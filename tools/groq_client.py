"""Shared Groq helpers: client, strict JSON-schema conversion, and free-tier-friendly retries.

Model: GROQ_MODEL in .env (default openai/gpt-oss-120b - the Groq production model that supports both
built-in browser search and strict structured outputs).

Free-tier notes (Nov 2026): gpt-oss-120b allows roughly 30 requests/min, 8K tokens/min and 200K tokens/day.
Calls here are kept small; on HTTP 429 we wait for the retry-after header and try again.
"""
import copy
import json
import os
import time

from dotenv import load_dotenv

from common import ROOT, fail

DEFAULT_MODEL = "openai/gpt-oss-120b"


def client_and_model():
    load_dotenv(ROOT / ".env")
    if not os.getenv("GROQ_API_KEY"):
        fail("GROQ_API_KEY is not set in .env (create one at console.groq.com/keys)")
    from groq import Groq
    return Groq(max_retries=0), os.getenv("GROQ_MODEL") or DEFAULT_MODEL


def strict_schema(model_cls, drop_fields=()) -> dict:
    """Pydantic model -> Groq strict json_schema: every property required, nullable for optional,
    additionalProperties false everywhere, no titles/defaults."""
    schema = copy.deepcopy(model_cls.model_json_schema())

    def walk(node):
        # node is always a schema (never a properties map), so "title"/"default" here are schema keywords.
        if isinstance(node, list):
            for v in node:
                walk(v)
            return
        if not isinstance(node, dict):
            return
        node.pop("title", None)
        node.pop("default", None)
        if "properties" in node:
            props = node["properties"]
            for f in drop_fields:
                props.pop(f, None)
            node["required"] = list(props.keys())
            node["additionalProperties"] = False
            for sub in props.values():   # walk each property's schema, not the map itself
                walk(sub)
        for key in ("items", "anyOf", "allOf", "oneOf", "$defs", "definitions"):
            if key in node:
                walk(list(node[key].values()) if isinstance(node[key], dict) else node[key])
    walk(schema)
    return schema


def chat(client, max_attempts=4, **kwargs):
    """chat.completions.create with handling for the free tier's rate limits."""
    import groq
    for attempt in range(1, max_attempts + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except groq.RateLimitError as e:
            wait = float(e.response.headers.get("retry-after", "20") or 20)
            body = str(getattr(e, "message", e))
            if "per day" in body.lower() or "tpd" in body.lower() or "rpd" in body.lower():
                fail(f"Groq daily free-tier limit reached - try again tomorrow. ({body[:200]})")
            if attempt == max_attempts:
                fail(f"Groq rate limit persists after {max_attempts} attempts: {body[:200]}")
            print(f"  Groq rate limit - waiting {wait:.0f}s (attempt {attempt}/{max_attempts})")
            time.sleep(min(wait + 1, 90))
        except groq.AuthenticationError:
            fail("Groq rejected GROQ_API_KEY - check the key in .env")
        except groq.APIStatusError as e:
            msg = str(getattr(e, "message", e))
            if e.status_code == 413 or "too large" in msg.lower():
                fail("Request is larger than the Groq free tier's tokens-per-minute limit. "
                     "Use a narrower topic or fewer findings, or upgrade the Groq plan. " + msg[:200])
            if e.status_code == 400 and "does not match the expected schema" in msg:
                if attempt == max_attempts:
                    fail(f"Groq output kept failing the schema: {msg[:300]}")
                print(f"  schema mismatch, retrying (attempt {attempt})")
                continue
            if e.status_code >= 500 and attempt < max_attempts:
                print(f"  Groq server error {e.status_code}, retrying in {5 * attempt}s")
                time.sleep(5 * attempt)
                continue
            fail(f"Groq API error {e.status_code}: {msg[:300]}")
        except groq.APIConnectionError:
            if attempt == max_attempts:
                fail("Network error reaching Groq")
            time.sleep(5 * attempt)


def structured(client, model, model_cls, system, user, name, max_tokens=8000, drop_fields=()):
    """One strict structured-output call; returns a validated pydantic instance."""
    resp = chat(client, model=model, max_completion_tokens=max_tokens, reasoning_effort="low",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": {
                    "name": name, "strict": True, "schema": strict_schema(model_cls, drop_fields)}})
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        fail(f"Groq output for '{name}' was cut off (max tokens) - narrow the topic and retry")
    return model_cls.model_validate(json.loads(choice.message.content)), resp.usage
