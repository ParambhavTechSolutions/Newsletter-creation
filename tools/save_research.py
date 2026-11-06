"""Validate a research draft, check every source URL, and save research.json.

Used two ways:
  - automatically by research_topic.py (Groq) after it structures its findings
  - manually as the fallback path, when the agent researches in session and writes
    .tmp/<slug>/research_draft.json itself:
        .venv/bin/python tools/save_research.py .tmp/<slug>/research_draft.json

It (1) validates the Research schema (tools/schemas.py), (2) pings each source URL, and
(3) sets verified_source=false on items whose URL is dead - or, when a list of URLs the
researcher actually opened is supplied, on items citing a URL outside that list.
Free - no API keys.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from pydantic import ValidationError

from common import ROOT, fail, load_json, slugify, write_json
from schemas import Research

ITEM_KEYS = ("key_facts", "statistics", "timeline", "quotes", "trends")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def check_url(url: str) -> str:
    """ok = page loads; blocked = site exists but refuses bots (401/403/429); dead = 404/410/DNS/timeout."""
    if not url.startswith(("http://", "https://")):
        return "dead"
    for method in ("head", "get"):
        try:
            r = requests.request(method, url, headers=HEADERS, timeout=12, allow_redirects=True, stream=True)
            r.close()
        except requests.RequestException:
            continue
        if r.status_code < 400:
            return "ok"
        if r.status_code in (401, 403, 429, 999):
            return "blocked"
        if method == "head" and r.status_code in (405, 501):
            continue
        return "dead"
    return "dead"


def norm(url: str) -> str:
    return url.split("#")[0].rstrip("/").lower()


def finalize(raw: dict, out_dir: Path, seen_urls=None) -> dict:
    try:
        research = Research.model_validate(raw)
    except ValidationError as e:
        print(e)
        fail(f"research draft doesn't match the schema ({e.error_count()} errors)")
    data = research.model_dump()
    data["slug"] = data.get("slug") or slugify(data["topic"])
    f = data["findings"]
    urls = sorted({i["source_url"] for k in ITEM_KEYS for i in f[k]})
    if not urls:
        fail("no source URLs in the research")

    print(f"Checking {len(urls)} source URLs...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        status = dict(zip(urls, pool.map(check_url, urls)))
    seen = {norm(u) for u in seen_urls} if seen_urls else None
    for u in urls:
        if seen is not None and norm(u) not in seen:
            status[u] = status[u] + ",not-opened"
    for u, s in status.items():
        if s != "ok":
            print(f"  {s:18} {u}")

    unverified = 0
    for k in ITEM_KEYS:
        for item in f[k]:
            s = status[item["source_url"]]
            item["verified_source"] = not s.startswith("dead") and "not-opened" not in s
            unverified += not item["verified_source"]

    data["citations"] = urls
    data["url_checks"] = status
    out = out_dir / "research.json"
    write_json(out, data)

    print(f"OK  {out.relative_to(ROOT)}")
    print(f"  facts={len(f['key_facts'])} stats={len(f['statistics'])} timeline={len(f['timeline'])} "
          f"quotes={len(f['quotes'])} trends={len(f['trends'])} sources={len(urls)} "
          f"(ok={sum(s == 'ok' for s in status.values())}, unverified items={unverified})")
    if unverified:
        print(f"  WARNING: {unverified} item(s) have verified_source=false (dead URL or a URL the researcher "
              f"never opened). They must not be used in the newsletter.")
    if len(f["statistics"]) < 4:
        print("  note: fewer than 4 statistics - favour timeline/quote/comparison/AI cards over charts")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("draft_json")
    args = ap.parse_args()
    draft_path = Path(args.draft_json).resolve()
    finalize(load_json(draft_path), draft_path.parent)


if __name__ == "__main__":
    main()
