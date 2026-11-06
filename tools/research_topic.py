"""Research a newsletter topic with Groq (gpt-oss-120b + built-in browser search) and save research.json.

Usage:
  .venv/bin/python tools/research_topic.py "AI in real estate" [--audience "..."] [--focus "angle to emphasise"]

Two Groq calls (browser search can't be combined with structured output):
  1. search  - gpt-oss-120b with the browser_search tool writes a sourced research brief
               -> .tmp/<slug>/research_brief.md  (+ research_search.json with every URL it opened)
  2. structure - strict JSON schema turns the brief into the Research findings, using only the brief
Then save_research.finalize() pings each URL and marks items whose URL is dead or was never opened
during the search as verified_source=false.

Cost: free on Groq's free tier (watch the ~200K tokens/day limit; one run is roughly 15-30K).
Requires: GROQ_API_KEY in .env
"""
import argparse
import json
import re
from datetime import date

from common import ROOT, fail, issue_dir, slugify, write_json
from groq_client import chat, client_and_model, structured
from save_research import finalize
from schemas import Findings

URL_RE = re.compile(r"https?://[^\s\)\]>\"'】]+")

SEARCH_SYSTEM = (
    "You are a meticulous research analyst preparing source material for a business newsletter. "
    "Use the browser_search tool several times with different queries, and open the most authoritative pages "
    "(industry reports, research firms, official statistics, major business publications; avoid vendor marketing "
    "and content farms). Prefer sources from the last 18 months. Cover the topic globally: find concrete examples from several regions (e.g. US, Europe, China, Southeast Asia, Middle East) and also search specifically for Indian sources (Indian business press, NASSCOM, government/RBI/MeitY data, Indian companies). Never invent or estimate numbers - only report "
    "what you read on a page. Quotes must be verbatim."
)

STRUCTURE_SYSTEM = (
    "You convert a research brief into structured JSON. Use ONLY information stated in the brief. "
    "Every item's source_url must be copied exactly from the brief and must be one of the allowed URLs. "
    "Drop any item without a clear source. statistics.value must be the plain number from the brief "
    "(e.g. 42 for 42%), with the unit separately (\"%\", \"USD billion\", \"hours\"). Do not round or convert. "
    "If the brief has fewer items than requested, return fewer - never pad. "
    "Put INDIA CONTEXT items into key_facts, each starting with \"India: \"."
)


def search_prompt(topic, audience, focus, today):
    return f"""Topic: {topic}
Audience: {audience}
{f"Angle to emphasise: {focus}" if focus else ""}
Today's date: {today}

Research this topic and write a research brief in plain text with these headings. After EVERY item put
" | SOURCE: <exact URL of the page you read it on>".

SUMMARY (3-4 sentences)
KEY FACTS (6-10 specific facts)
STATISTICS (6-12 numbers: label, value, unit, year, one line of context. Include comparable series where you can,
  e.g. the same metric across years or segments from one source)
TIMELINE (4-8 dated milestones)
QUOTES (2-4 verbatim quotes with speaker name and role)
TRENDS (3-5 trends with one line of detail)
INDIA CONTEXT (2-5 facts about adoption, costs, regulation or players in India - each from an Indian or India-specific source; write "none found" rather than guess)
BUSINESS IMPLICATIONS (3-5 practical implications for medium-sized, traditional businesses in India; no source needed)"""


def opened_urls(message) -> set:
    urls = set()
    for t in message.executed_tools or []:
        for b in t.browser_results or []:
            if b.url:
                urls.add(b.url)
        if t.search_results and t.search_results.results:
            urls |= {r.url for r in t.search_results.results if r.url}
        urls |= set(URL_RE.findall(t.output or ""))
    return urls


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("topic")
    ap.add_argument("--audience", default="owners and leaders of medium-sized, traditional businesses in India")
    ap.add_argument("--focus", default="", help="optional angle, e.g. 'cost savings for small brokerages'")
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()

    client, model = client_and_model()
    slug = args.slug or slugify(args.topic)
    d = issue_dir(slug)
    today = date.today().isoformat()

    # ---- 1. search ------------------------------------------------------------------------
    print(f"1/2 Searching the web with {model} (browser_search)...")
    resp = chat(client, model=model, max_completion_tokens=6000, reasoning_effort="low",
                tools=[{"type": "browser_search"}], tool_choice="required",
                messages=[{"role": "system", "content": SEARCH_SYSTEM},
                          {"role": "user", "content": search_prompt(args.topic, args.audience, args.focus, today)}])
    msg = resp.choices[0].message
    brief = (msg.content or "").strip()
    if not brief:
        fail("Groq returned an empty research brief - retry, or narrow the topic")
    seen = opened_urls(msg)
    brief_urls = set(URL_RE.findall(brief))
    (d / "research_brief.md").write_text(brief)
    write_json(d / "research_search.json", {"opened_urls": sorted(seen), "brief_urls": sorted(brief_urls),
                                            "usage": resp.usage.model_dump() if resp.usage else {}})
    print(f"  brief: {len(brief)} chars, {len(brief_urls)} cited URLs, {len(seen)} URLs opened by the search tool")
    if not brief_urls:
        fail("The brief cites no URLs - can't verify anything. Retry the research.")

    # ---- 2. structure ---------------------------------------------------------------------
    print("2/2 Structuring findings (strict JSON schema)...")
    allowed = sorted(brief_urls)
    findings, usage = structured(
        client, model, Findings, STRUCTURE_SYSTEM,
        f"Allowed source URLs:\n" + "\n".join(allowed) + f"\n\n<brief>\n{brief}\n</brief>",
        name="research_findings", max_tokens=6000, drop_fields=("verified_source",))

    raw = {"topic": args.topic, "slug": slug, "audience": args.audience, "researched_on": today,
           "findings": findings.model_dump()}
    # If the search tool reported which pages it opened, only those count as verified sources.
    finalize(raw, d, seen_urls=seen or None)


if __name__ == "__main__":
    main()
