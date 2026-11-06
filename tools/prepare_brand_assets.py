"""Prepare email-ready logo PNGs from the brand master files.

Trims the large empty canvas around each logo (keeping clear space), and
resizes to 2x the display width so logos stay sharp on retina screens.
Never recolours, stretches or changes proportions (brand guideline 02).

Usage: .venv/bin/python tools/prepare_brand_assets.py
Run once, or again whenever the brand_assests/ files change.
"""
from PIL import Image, ImageChops

from common import ROOT, load_brand


def content_bbox(im: Image.Image):
    """Bounding box of non-background pixels (alpha or solid-bg images)."""
    if im.mode == "RGBA":
        return im.split()[3].getbbox()
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg).convert("L").point(lambda p: 255 if p > 12 else 0)
    return diff.getbbox()


def trim_with_clearspace(src, dst, display_width, pad_ratio):
    im = Image.open(src)
    box = content_bbox(im)
    if not box:
        raise SystemExit(f"ERROR: could not find logo content in {src}")
    left, top, right, bottom = box
    # Clear space ~ height of the lower symbol stroke; approximated as a ratio of logo height.
    pad = int((bottom - top) * pad_ratio)
    box = (max(0, left - pad), max(0, top - pad), min(im.width, right + pad), min(im.height, bottom + pad))
    cropped = im.crop(box)
    target_w = display_width * 2
    if cropped.width > target_w:
        h = round(cropped.height * target_w / cropped.width)  # keep proportions exactly
        cropped = cropped.resize((target_w, h), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dst, optimize=True)
    print(f"  {dst.relative_to(ROOT)}  {cropped.size[0]}x{cropped.size[1]}px")


def main():
    logo = load_brand()["logo"]
    print("Preparing email logo assets:")
    trim_with_clearspace(ROOT / logo["source_dark"], ROOT / logo["email_dark"], logo["header_display_width"], 0.12)
    trim_with_clearspace(ROOT / logo["source_light"], ROOT / logo["email_light"], logo["header_display_width"], 0.12)
    trim_with_clearspace(ROOT / logo["source_symbol"], ROOT / logo["email_symbol"], logo["symbol_display_width"], 0.08)
    print("OK")


if __name__ == "__main__":
    main()
