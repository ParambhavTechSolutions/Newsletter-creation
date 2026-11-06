"""Validate a built newsletter against the Parambhaav Tech brand guidelines.

Usage: .venv/bin/python tools/brand_check.py .tmp/<slug>/newsletter.html

Checks:
  1. Only palette colours appear in the HTML (brand guideline 03)
  2. Every declared text/background pair in brand.json meets its WCAG contrast minimum (guideline 08)
  3. Header logo is displayed at >= min_display_width px (guideline 02)
  4. Every <img> has alt text; no <svg>/<script> (Gmail strips them)
  5. HTML size under Gmail's ~102KB clipping limit
Exit code 1 if any check fails.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from common import contrast_ratio, load_brand

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


class ImgCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.imgs, self.forbidden = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.imgs.append(dict(attrs))
        elif tag in ("svg", "script"):
            self.forbidden.append(tag)


def expand(h):
    h = h.lower()
    return "#" + "".join(ch * 2 for ch in h[1:]) if len(h) == 4 else h


def check(html_path: Path):
    brand = load_brand()
    colors = brand["colors"]
    palette = {v.lower() for v in colors.values()}
    html = html_path.read_text()
    problems, notes = [], []

    # Strip href/anchor values so "#src1" style fragments aren't mistaken for colours
    scan = re.sub(r'(href|name)="[^"]*"', "", html)
    found = {expand(h) for h in HEX_RE.findall(scan)}
    off = sorted(found - palette)
    if off:
        problems.append(f"Off-palette colours used: {', '.join(off)}")
    else:
        notes.append(f"Colours: {len(found)} used, all on-palette")

    for p in brand["contrast_pairs"]:
        r = contrast_ratio(colors[p["fg"]], colors[p["bg"]])
        if r < p["min"]:
            problems.append(f"Contrast {p['fg']} on {p['bg']} = {r:.2f}:1 < {p['min']} ({p['use']})")
    notes.append(f"Contrast: {len(brand['contrast_pairs'])} brand pairs checked")

    parser = ImgCollector()
    parser.feed(html)
    missing_alt = [i.get("src", "?") for i in parser.imgs if not (i.get("alt") or "").strip()]
    if missing_alt:
        problems.append(f"Images without alt text: {missing_alt}")
    logo = [i for i in parser.imgs if "brand-logo" in (i.get("class") or "")]
    min_w = brand["logo"]["min_display_width"]
    if not logo:
        problems.append("Header logo not found (img.brand-logo)")
    elif int(logo[0].get("width", 0)) < min_w:
        problems.append(f"Logo displayed at {logo[0].get('width')}px < minimum {min_w}px")
    if parser.forbidden:
        problems.append(f"Email contains tags Gmail strips: {sorted(set(parser.forbidden))}")
    notes.append(f"Images: {len(parser.imgs)}, all with alt text" if not missing_alt else "")

    kb = len(html.encode()) / 1024
    limit = brand["email"]["gmail_clip_limit_kb"]
    if kb > limit:
        problems.append(f"HTML is {kb:.0f}KB > {limit}KB - Gmail will clip the message")
    notes.append(f"Size: {kb:.0f}KB (limit {limit}KB)")

    return problems, [n for n in notes if n]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    problems, notes = check(Path(sys.argv[1]))
    for n in notes:
        print(f"  pass  {n}")
    for p in problems:
        print(f"  FAIL  {p}")
    if problems:
        sys.exit(1)
    print("OK  brand check passed")


if __name__ == "__main__":
    main()
