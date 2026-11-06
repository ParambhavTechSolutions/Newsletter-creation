"""Validate the agent-written content.json before rendering: schema, fact integrity and brand voice.

Usage: .venv/bin/python tools/check_content.py .tmp/<slug>/content.json

Checks:
  - structure matches the Newsletter schema (tools/schemas.py); required fields per infographic type
  - every [n] citation has a source, every source is cited, every source URL is in research.json
  - every infographic number (stats values, chart data) appears in research.json findings
  - infographics are attached to exactly one section; ids unique
  - AI image prompts contain no digits/text requests
  - brand voice: no hype words or guaranteed-result phrasing (config/brand.json voice.dont)
  - business takeaway addresses Indian businesses
  - subject/preview length
Exit 1 on errors (schema, broken citations, unattached/unknown infographics); warnings print but pass.
Free - no API keys.
"""
import argparse
import json
import re
from pathlib import Path

from pydantic import ValidationError

from common import fail, load_json
from schemas import Newsletter

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
TYPE_FIELDS = {"stats": ["stats"], "chart": ["chart"], "timeline": ["events"], "comparison": ["left", "right"],
               "quote": ["quote", "speaker"], "ai": ["prompt"]}
HYPE = ["revolutionary", "revolutionise", "revolutionize", "game-changing", "game changer", "disrupt", "unleash",
        "supercharge", "skyrocket", "cutting-edge", "next-gen", "paradigm", "synergy", "guaranteed", "guarantee",
        "10x your", "secret weapon", "unlock the power"]


def nums(text: str) -> set:
    out = set()
    for n in NUM_RE.findall(str(text)):
        n = n.replace(",", "")
        out.add(n)
        out.add(str(float(n)).rstrip("0").rstrip("."))
    return out


def check(n: dict, research: dict):
    errors, warns = [], []

    texts = n["intro"] + n["key_takeaways"] + n["business_takeaway"]["body"] + \
        [p for s in n["sections"] for p in s["body"]] + [f["point"] for f in n["business_takeaway"]["focus_areas"]]
    src_ns = [s["n"] for s in n["sources"]]
    if len(src_ns) != len(set(src_ns)):
        errors.append("duplicate source numbers")
    used = {int(x) for t in texts for x in re.findall(r"\[(\d+)\]", t)}
    if used - set(src_ns):
        errors.append(f"citations without a source entry: {sorted(used - set(src_ns))}")
    if set(src_ns) - used:
        warns.append(f"sources never cited in text: {sorted(set(src_ns) - used)}")

    if research:
        f = research["findings"]
        research_urls = set(research.get("citations") or [])
        dead = {u for u, s in (research.get("url_checks") or {}).items() if s == "dead"}
        for s in n["sources"]:
            if s["url"] not in research_urls:
                warns.append(f"source [{s['n']}] URL not in research.json: {s['url']}")
            if s["url"] in dead:
                errors.append(f"source [{s['n']}] URL is dead: {s['url']}")
        research_nums = nums(json.dumps(f))
    else:
        warns.append("research.json not found next to content.json - number tracing skipped")
        research_nums = None

    ids = [g["id"] for g in n["infographics"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate infographic ids")
    refs = [s["infographic"] for s in n["sections"] if s.get("infographic")]
    for r in refs:
        if r not in ids:
            errors.append(f"section references unknown infographic '{r}'")
    for g in set(ids) - set(refs):
        errors.append(f"infographic '{g}' is not attached to any section")
    for r in {r for r in refs if refs.count(r) > 1}:
        warns.append(f"infographic '{r}' is attached to more than one section")
    if not 3 <= len(ids) <= 5:
        warns.append(f"{len(ids)} infographics (aim for 3-5)")
    if sum(g["type"] == "ai" for g in n["infographics"]) > 1:
        warns.append("more than one AI illustration - keep it to one per issue")

    for g in n["infographics"]:
        missing = [k for k in TYPE_FIELDS[g["type"]] if not g.get(k)]
        if missing:
            errors.append(f"infographic '{g['id']}' ({g['type']}) missing: {missing}")
        vals = []
        if g["type"] == "stats":
            vals = [s["value"] for s in g.get("stats") or []]
        elif g["type"] == "chart" and g.get("chart"):
            c = g["chart"]
            vals = [f"{x:g}" for d in c["datasets"] for x in d["data"]]
            for d in c["datasets"]:
                if len(d["data"]) != len(c["labels"]):
                    errors.append(f"infographic '{g['id']}': {len(c['labels'])} labels but {len(d['data'])} values")
        if research_nums is not None:
            for v in vals:
                if nums(v) and not (nums(v) & research_nums):
                    warns.append(f"infographic '{g['id']}': value {v} not found in research - verify or remove")
        if g["type"] == "ai" and re.search(r"\d|text|word|label|logo|chart|graph", g.get("prompt") or "", re.I):
            warns.append(f"infographic '{g['id']}': AI prompt mentions digits/text/charts - image models garble these")

    blob = " ".join(texts + [n["headline"], n["dek"], n["subject"]]).lower()
    for w in HYPE:
        if w in blob:
            warns.append(f"brand voice: avoid '{w}'")
    bt_text = " ".join([n["business_takeaway"].get("heading") or ""] + n["business_takeaway"]["body"]).lower()
    if "india" not in bt_text:
        warns.append("business_takeaway never mentions India - close with how Indian businesses can apply this")
    if len(n["subject"]) > 60:
        warns.append(f"subject is {len(n['subject'])} chars (aim <= 60)")
    if not 40 <= len(n["preview_text"]) <= 140:
        warns.append(f"preview_text is {len(n['preview_text'])} chars (aim 40-140)")
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("content_json")
    args = ap.parse_args()

    path = Path(args.content_json).resolve()
    raw = load_json(path)
    try:
        n = Newsletter.model_validate(raw).model_dump(exclude_none=True)
    except ValidationError as e:
        print(e)
        fail(f"content.json doesn't match the schema ({e.error_count()} errors)")
    rp = path.parent / "research.json"
    research = load_json(rp) if rp.exists() else None

    errors, warns = check(n, research)
    for w in warns:
        print(f"  warn  {w}")
    for e in errors:
        print(f"  FAIL  {e}")
    if errors:
        fail(f"{len(errors)} error(s) in content.json")
    print(f"OK  content.json valid ({len(n['sections'])} sections, {len(n['infographics'])} infographics, "
          f"{len(n['sources'])} sources, {len(warns)} warning(s))")


if __name__ == "__main__":
    main()
