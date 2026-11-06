"""Write content.json from research.json with Groq, in the Parambhaav Tech brand voice.

Usage:
  .venv/bin/python tools/write_newsletter.py .tmp/<slug>/research.json [--no-ai-images]

Two strict-JSON Groq calls (kept small for the free tier's tokens-per-minute limit):
  1. article  - subject, headline, intro, takeaways, sections, closing, sources
  2. visuals  - 3-5 infographics, each attached to one section
Merged into .tmp/<slug>/content.json, then validated with check_content (citations, numbers traced to
research, brand voice). Only research items with verified_source=true are given to the model.

Cost: free on Groq's free tier. Requires: GROQ_API_KEY in .env
Review the warnings and content.json before rendering - it is the editorial checkpoint.
"""
import argparse
import json
import re
from pathlib import Path
from typing import List, Literal, Optional

from check_content import check
from common import ROOT, fail, load_brand, load_json, write_json
from groq_client import client_and_model, structured
from schemas import BusinessTakeaway, Chart, Column, Event, Newsletter, Source, Stat, Strict

ITEM_KEYS = ("key_facts", "statistics", "timeline", "quotes", "trends")


# ---- call-specific schemas -------------------------------------------------------------
class ArticleSection(Strict):
    heading: str
    body: List[str]


class Article(Strict):
    subject: str
    preview_text: str
    eyebrow: Optional[str]
    headline: str
    dek: str
    intro: List[str]
    key_takeaways: List[str]
    sections: List[ArticleSection]
    business_takeaway: BusinessTakeaway
    sources: List[Source]


class Visual(Strict):
    section_index: int
    type: Literal["stats", "chart", "timeline", "comparison", "quote", "ai"]
    theme: Literal["dark", "light"]
    eyebrow: Optional[str]
    title: str
    subtitle: Optional[str]
    alt: str
    source: str
    stats: Optional[List[Stat]]
    chart: Optional[Chart]
    events: Optional[List[Event]]
    left: Optional[Column]
    right: Optional[Column]
    quote: Optional[str]
    speaker: Optional[str]
    role: Optional[str]
    prompt: Optional[str]
    caption: Optional[str]


class Visuals(Strict):
    infographics: List[Visual]


# ---- prompts ----------------------------------------------------------------------------
def voice(brand):
    v = brand["voice"]
    return (f'You write "{brand["newsletter_name"]}", the newsletter of {brand["name"]} - {brand["tagline"]}.\n'
            f'{brand["elevator_pitch"]}\nReaders: {brand["market"]["readers"]}. '
            f'Busy, practical, not technical.\nEDITORIAL ANGLE: {brand["market"]["editorial_angle"]}\nVOICE - do: {"; ".join(v["do"])}. Don\'t: {"; ".join(v["dont"])}.\n')


def article_system(brand):
    return voice(brand) + f"""
FACT INTEGRITY (non-negotiable): use only facts, numbers and quotes in the research JSON. Never invent, round,
combine or extrapolate numbers. Cite with [n] markers in intro, takeaways, section bodies and focus-area points.
`sources` lists each cited URL once (copied exactly from the research), numbered from 1 in order of first use.
Every [n] must exist in sources; every source must be cited. Quotes verbatim.

STRUCTURE
- subject <= 60 characters, specific, no clickbait or emoji. preview_text 60-120 characters, adds to the subject.
- eyebrow: 1-3 word label or null. headline: clear, outcome-led. dek: one sentence.
- intro: 1-2 short paragraphs. key_takeaways: 3-4 one-sentence bullets.
- sections: 3-5, each a heading and 1-3 paragraphs of 2-4 sentences. Concrete examples over abstractions.
  Sections explore the technology worldwide: name the country/region of each example. At most one section is India-only.
  If the research has no India facts, say so plainly rather than inventing an Indian angle.
- business_takeaway: heading "{brand['voice']['closing_section_heading']}", 1-2 paragraphs on how Indian businesses can
  apply what the global examples show (practical first steps, cited where a fact is used);
  focus_areas only for Real Estate / EduTech / Digital Services where the topic genuinely applies (can be empty).
- **bold** at most once per paragraph."""


def visuals_system(brand, allow_ai):
    ai = ("- type \"ai\": at most ONE, usually for section 0. `prompt` describes a scene or concept (people, places, "
          "workflows) in under 60 words - never text, words, numbers, charts, logos or screens with text. Don't describe "
          "colours (the brand style is added automatically). source \"AI illustration\".\n"
          if allow_ai else "- Do NOT use type \"ai\".\n")
    return voice(brand) + f"""
Design 3-5 infographics for the newsletter below. Each attaches to one section via section_index (0-based);
use each section at most once. Alternate theme dark/light. Use ONLY numbers that appear in the research JSON,
exactly as given. Fill only the fields for the chosen type and set every other field to null.
- "stats": 2-4 headline numbers; value is the number as text ("42"), unit like "%", "x", "hrs", "USD bn".
- "chart": only for a comparable series (same metric and source). kind bar (years/categories), hbar (long labels),
  line (trend), doughnut (parts of a whole summing to ~100). labels and each dataset's data must be the same length.
  highlight_index marks the key bar (or null); unit "%" etc. Caveats (survey, region, year) go in subtitle.
- "timeline": 3-6 dated events. "comparison": left/right columns (e.g. manual vs digital), 3-5 short items each.
- "quote": one verbatim quote from the research with speaker and role.
{ai}- title: short and specific. alt: describe what the visual shows including key numbers.
- source: short publisher name(s) of the data."""


def slim_research(research):
    f = research["findings"]
    keep = {k: [{kk: vv for kk, vv in i.items() if kk != "verified_source"}
                for i in f[k] if i.get("verified_source", True)] for k in ITEM_KEYS}
    keep["summary"] = f["summary"]
    keep["business_implications"] = f["business_implications"]
    return {"topic": research["topic"], "audience": research["audience"], "findings": keep}


def slugid(text, used):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30] or "visual"
    i, out = 2, base
    while out in used:
        out, i = f"{base}-{i}", i + 1
    used.add(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("research_json")
    ap.add_argument("--no-ai-images", action="store_true")
    args = ap.parse_args()

    research_path = Path(args.research_json).resolve()
    research = load_json(research_path)
    brand = load_brand()
    slim = slim_research(research)
    if not any(slim["findings"][k] for k in ITEM_KEYS):
        fail("research.json has no verified items to write from")
    log = ROOT / "issues_log.json"
    recent = json.loads(log.read_text())[-8:] if log.exists() else []
    recent_txt = "\n".join(f"- {r.get('subject')}" for r in recent) or "- none yet"
    research_txt = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

    client, model = client_and_model()
    print(f"1/2 Writing the article with {model}...")
    article, u1 = structured(client, model, Article, article_system(brand),
                             f"Recent issues (avoid repeating their angle):\n{recent_txt}\n\n<research>{research_txt}</research>",
                             name="newsletter_article", max_tokens=6000)
    a = article.model_dump()

    print("2/2 Designing infographics...")
    outline = "\n".join(f"{i}. {s['heading']} - {s['body'][0][:160]}" for i, s in enumerate(a["sections"]))
    visuals, u2 = structured(client, model, Visuals, visuals_system(brand, not args.no_ai_images),
                             f"Sections:\n{outline}\n\n<research>{research_txt}</research>",
                             name="newsletter_visuals", max_tokens=5000)

    used_ids, used_sections, infographics = set(), set(), []
    sections = [dict(s) for s in a["sections"]]
    for v in visuals.model_dump()["infographics"]:
        idx = v.pop("section_index")
        if not 0 <= idx < len(sections) or idx in used_sections:
            print(f"  skip  infographic '{v['title']}' (section {idx} invalid or already used)")
            continue
        used_sections.add(idx)
        v["id"] = slugid(v["title"], used_ids)
        if v["type"] == "ai":
            v["aspect"] = "16:9"
        infographics.append({k: val for k, val in v.items() if val is not None})
        sections[idx]["infographic"] = v["id"]

    content = {"topic": research["topic"], **{k: a[k] for k in ("subject", "preview_text", "eyebrow", "headline", "dek",
               "intro", "key_takeaways")}, "sections": sections, "infographics": infographics,
               "business_takeaway": a["business_takeaway"], "sources": a["sources"]}
    content = Newsletter.model_validate(content).model_dump(exclude_none=True)
    out = research_path.parent / "content.json"
    write_json(out, content)
    tokens = sum(getattr(u, "total_tokens", 0) or 0 for u in (u1, u2))
    print(f"OK  {out.relative_to(ROOT)} ({len(sections)} sections, {len(infographics)} infographics, "
          f"{len(content['sources'])} sources; {tokens} Groq tokens)")

    errors, warns = check(content, research)
    for w in warns:
        print(f"  warn  {w}")
    for e in errors:
        print(f"  FAIL  {e}")
    if errors:
        fail(f"{len(errors)} error(s) - fix content.json by hand (then run check_content.py) or rerun")
    if not warns:
        print("  pass  integrity checks")


if __name__ == "__main__":
    main()
