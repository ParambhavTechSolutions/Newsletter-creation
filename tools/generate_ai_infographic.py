"""Generate an on-brand illustration for free with Cloudflare Workers AI (FLUX.1 schnell).

Usage (standalone):
  .venv/bin/python tools/generate_ai_infographic.py "a property manager reviewing a digital dashboard" \
      --out .tmp/<slug>/img/hero_raw.png [--aspect 16:9] [--steps 8]

Normally called by render_infographics.py for infographics with "type": "ai".
The brand style anchor from config/brand.json (ai_image_style) is appended to every prompt.

Rules: AI images are for concepts and scenes only. Never ask for numbers, charts or text -
image models garble them. Data visuals use the stats/chart/timeline cards instead.

Cost: FREE on the Cloudflare Workers Free plan (10,000 neurons/day; one 1024px image at 8 steps
is roughly 100 neurons). When the daily allowance runs out, requests fail until 00:00 UTC.
FLUX.1 schnell outputs a 1024x1024 JPEG; it is center-cropped to the requested aspect ratio.
A sidecar <out>.json stores the prompt hash; the same prompt reuses the saved image.
Requires: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env
"""
import argparse
import base64
import hashlib
import io
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from common import ROOT, fail, load_brand

MODEL = "@cf/black-forest-labs/flux-1-schnell"
ASPECTS = {"16:9": 16 / 9, "4:3": 4 / 3, "3:2": 3 / 2, "1:1": 1.0}
PROMPT_LIMIT = 2048


def _creds():
    load_dotenv(ROOT / ".env")
    acct, token = os.getenv("CLOUDFLARE_ACCOUNT_ID"), os.getenv("CLOUDFLARE_API_TOKEN")
    if not acct or not token:
        fail("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set in .env "
             "(dash.cloudflare.com -> Workers AI -> Use REST API)")
    return acct, token


def center_crop(img: Image.Image, aspect: float) -> Image.Image:
    w, h = img.size
    if w / h > aspect:
        nw = round(h * aspect)
        return img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w / aspect)
    return img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def generate(subject: str, out: Path, aspect: str = "16:9", steps: int = 8, force: bool = False,
             retries: int = 3) -> Path:
    brand = load_brand()
    if aspect not in ASPECTS:
        fail(f"aspect must be one of {sorted(ASPECTS)}")
    prompt = f"{subject.strip()}. Style: {brand['ai_image_style']}"
    if len(prompt) > PROMPT_LIMIT:
        fail(f"prompt is {len(prompt)} chars; FLUX accepts {PROMPT_LIMIT}. Shorten the scene description.")
    digest = hashlib.sha256(f"{MODEL}|{prompt}|{aspect}|{steps}".encode()).hexdigest()[:16]
    out = Path(out)
    meta = out.with_suffix(".json")
    if not force and out.exists() and meta.exists() and json.loads(meta.read_text()).get("hash") == digest:
        print(f"  cached {out.relative_to(ROOT)} (same prompt)")
        return out

    acct, token = _creds()
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}"
    # The Workers AI flux-1-schnell endpoint rejects a "seed" field; each call is already a fresh random image.
    body = {"prompt": prompt, "steps": max(1, min(steps, 8))}
    err = ""
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=120)
        except requests.RequestException as e:
            err = str(e)
        else:
            if r.status_code == 200:
                payload = r.json()
                b64 = (payload.get("result") or {}).get("image") or payload.get("image")
                if not b64:
                    fail(f"Cloudflare returned no image: {str(payload)[:300]}")
                img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                img = center_crop(img, ASPECTS[aspect])
                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(out, "PNG", optimize=True)
                meta.write_text(json.dumps({"hash": digest, "model": MODEL, "steps": body["steps"],
                                            "aspect": aspect, "prompt": prompt}, indent=2))
                print(f"  OK   {out.relative_to(ROOT)} ({img.size[0]}x{img.size[1]}, free)")
                return out
            msg = r.text[:300]
            if r.status_code in (401, 403):
                fail(f"Cloudflare auth failed ({r.status_code}) - check the API token has Workers AI permission. {msg}")
            if r.status_code == 429 or "neuron" in msg.lower() or "limit" in msg.lower():
                fail("Cloudflare free daily limit reached (resets 00:00 UTC). Rerun later or drop the AI card. " + msg)
            err = f"HTTP {r.status_code}: {msg}"
        if attempt < retries:
            print(f"  attempt {attempt} failed ({err}); retrying in {5 * attempt}s")
            time.sleep(5 * attempt)
    fail(f"Cloudflare image generation failed after {retries} attempts: {err}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("subject", help="what the image should show (no text/numbers)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--aspect", default="16:9", choices=sorted(ASPECTS))
    ap.add_argument("--steps", type=int, default=8, help="1-8; more = better quality (still free)")
    ap.add_argument("--force", action="store_true", help="regenerate even if cached (new random image)")
    args = ap.parse_args()
    generate(args.subject, Path(args.out).resolve(), args.aspect, args.steps, args.force)


if __name__ == "__main__":
    main()
