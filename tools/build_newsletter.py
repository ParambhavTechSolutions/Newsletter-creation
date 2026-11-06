"""Build the branded, email-safe newsletter HTML (+ preview PNG and plain-text version).

Usage: .venv/bin/python tools/build_newsletter.py .tmp/<slug>/content.json [--no-preview]

Inputs:  content.json, img/*.png (from render_infographics.py), config/brand.json
Outputs (next to content.json):
  newsletter.html   email HTML with CSS inlined and images as cid: references (for Gmail)
  newsletter.txt    plain-text alternative part
  images.json       cid -> file map used by send_via_gmail.py
  preview.html/png  same email with local image paths, screenshotted for visual review
Runs brand_check at the end; exits 1 if the brand check fails.
"""
import argparse
import logging
import re
import textwrap
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context
from markupsafe import Markup, escape
from premailer import Premailer

from brand_check import check as brand_check
from common import ROOT, TEMPLATES, fail, load_brand, load_json, write_json

logging.getLogger("cssutils").setLevel(logging.CRITICAL)
CITE_RE = re.compile(r"\[(\d+)\]")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def make_rich(sources, charcoal):
    urls = {s["n"]: s["url"] for s in sources}

    def rich(text, cite_color=None):   # cite_color: pass the text colour on dark backgrounds
        t = str(escape(text))
        t = BOLD_RE.sub(r"<strong>\1</strong>", t)

        def cite(m):
            n = int(m.group(1))
            if n not in urls:
                raise ValueError(f"Citation [{n}] has no matching entry in sources")
            return (f'<sup style="font-size:11px; line-height:0;"><a href="{escape(urls[n])}" '
                    f'style="color:{cite_color or charcoal}; text-decoration:none; font-weight:700;">[{n}]</a></sup>')
        return Markup(CITE_RE.sub(cite, t))
    return rich


def plain_text(n, brand):
    strip = lambda s: BOLD_RE.sub(r"\1", s)
    wrap = lambda s: textwrap.fill(strip(s), 72)
    out = [brand["newsletter_name"].upper() + "  |  " + n["issue_label"], "", n["headline"].upper(), ""]
    if n.get("dek"):
        out += [wrap(n["dek"]), ""]
    out += [wrap(p) + "\n" for p in n.get("intro", [])]
    if n.get("key_takeaways"):
        out += ["IN 60 SECONDS"] + [textwrap.fill("- " + strip(t), 72, subsequent_indent="  ") for t in n["key_takeaways"]] + [""]
    for s in n["sections"]:
        out += ["", s["heading"].upper(), "-" * len(s["heading"])] + [wrap(p) + "\n" for p in s["body"]]
    bt = n.get("business_takeaway")
    if bt:
        out += ["", (bt.get("heading") or brand["voice"]["closing_section_heading"]).upper()]
        out += [wrap(p) + "\n" for p in bt.get("body", [])]
        out += [textwrap.fill(f"{fa['name']}: {strip(fa['point'])}", 72) for fa in bt.get("focus_areas", [])]
    if n.get("sources"):
        out += ["", "SOURCES"] + [f"[{s['n']}] {s['title']} - {s['url']}" for s in n["sources"]]
    out += ["", "--", f"{brand['name']} | {brand['tagline']}", brand["elevator_pitch"]]
    return "\n".join(out)


def validate(n):
    for k in ("subject", "preview_text", "headline", "sections", "sources"):
        if not n.get(k):
            fail(f"content.json missing required field: {k}")
    if len(n["subject"]) > 70:
        print(f"  warn  subject is {len(n['subject'])} chars; aim for <= 60 so it isn't truncated")
    if not 40 <= len(n["preview_text"]) <= 140:
        print(f"  warn  preview_text is {len(n['preview_text'])} chars; aim for 40-140")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("content_json")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    content_path = Path(args.content_json).resolve()
    d = content_path.parent
    n = load_json(content_path)
    brand = load_brand()
    validate(n)
    n.setdefault("issue_label", date.today().strftime("%d %B %Y"))

    graphics = {g["id"]: g for g in n.get("infographics", [])}
    images = {"logo": ROOT / brand["logo"]["email_dark"], "symbol": ROOT / brand["logo"]["email_symbol"]}
    for s in n["sections"]:
        gid = s.get("infographic")
        if gid:
            if gid not in graphics:
                fail(f"Section '{s['heading']}' references unknown infographic '{gid}'")
            png = d / "img" / f"{gid}.png"
            if not png.exists():
                fail(f"Missing {png.relative_to(ROOT)} - run render_infographics.py first")
            images[gid] = png
    for name, path in images.items():
        if not Path(path).exists():
            fail(f"Missing image {path} (run tools/prepare_brand_assets.py for logos)")

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True, undefined=StrictUndefined)
    try:
        env.filters["rich"] = make_rich(n["sources"], brand["colors"]["charcoal"])
    except KeyError as e:
        fail(f"Each source needs n, title, url ({e})")
    tpl = env.get_template("newsletter.html.j2")
    for k in ("eyebrow", "dek", "intro", "key_takeaways", "business_takeaway"):
        n.setdefault(k, None if k in ("eyebrow", "dek", "business_takeaway") else [])
    for s in n["sections"]:
        s.setdefault("infographic", None)
    if n["business_takeaway"]:
        n["business_takeaway"].setdefault("heading", None)
        n["business_takeaway"].setdefault("focus_areas", [])
    for s in n["sources"]:
        s.setdefault("publisher", None)

    ctx = dict(n=n, b=brand, c=brand["colors"], w=brand["email"]["width"], graphics=graphics)

    def render(img_fn):
        try:
            html = tpl.render(img=img_fn, **ctx)
        except ValueError as e:
            fail(str(e))
        return Premailer(html, keep_style_tags=True, strip_important=False, remove_classes=False,
                         allow_network=False, disable_validation=True,
                         cssutils_logging_level=logging.CRITICAL).transform()

    email_html = render(lambda name: f"cid:{name}")
    preview_html = render(lambda name: Path(images[name]).resolve().as_uri())

    (d / "newsletter.html").write_text(email_html)
    (d / "preview.html").write_text(preview_html)
    (d / "newsletter.txt").write_text(plain_text(n, brand))
    write_json(d / "images.json", {k: str(Path(v).resolve()) for k, v in images.items()})
    print(f"OK  {(d / 'newsletter.html').relative_to(ROOT)}  ({len(email_html.encode()) / 1024:.0f}KB, {len(images)} inline images)")

    if not args.no_preview:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 680, "height": 900}, device_scale_factor=1)
            page.goto((d / "preview.html").as_uri(), wait_until="networkidle")
            page.screenshot(path=str(d / "preview.png"), full_page=True)
            page.set_viewport_size({"width": 375, "height": 800})
            page.screenshot(path=str(d / "preview_mobile.png"), full_page=True)
            browser.close()
        print(f"OK  {(d / 'preview.png').relative_to(ROOT)} (+ preview_mobile.png)")

    print("Brand check:")
    problems, notes = brand_check(d / "newsletter.html")
    for x in notes:
        print(f"  pass  {x}")
    for x in problems:
        print(f"  FAIL  {x}")
    if problems:
        fail("Brand check failed - fix before creating the Gmail draft")
    print("OK  brand check passed")


if __name__ == "__main__":
    main()
