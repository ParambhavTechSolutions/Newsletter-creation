"""Shared helpers for newsletter tools: paths, brand config, slugs, contrast math."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
TEMPLATES = TOOLS / "templates"
TMP = ROOT / ".tmp"
BRAND_PATH = ROOT / "config" / "brand.json"


def load_brand() -> dict:
    return json.loads(BRAND_PATH.read_text())


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "newsletter"


def issue_dir(slug: str) -> Path:
    d = TMP / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except json.JSONDecodeError as e:
        fail(f"Invalid JSON in {path}: {e}")


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# --- WCAG contrast -------------------------------------------------------
def _channel(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)
