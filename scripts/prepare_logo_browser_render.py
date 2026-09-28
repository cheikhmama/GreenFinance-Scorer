"""Prepare local-only SVG rendering in Chromium, with no labels or headers."""
import base64
import json
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "technology_logos_assets"
items = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
parts = ["""<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: 160mm 100mm; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: white; }
.page { width: 160mm; height: 100mm; break-after: page; display: flex;
  align-items: center; justify-content: center; overflow: hidden; }
.page:last-child { break-after: auto; }
img { max-width: 150mm; max-height: 90mm; width: 150mm; height: 90mm; object-fit: contain; }
</style></head><body>"""]
for item in items:
    path = ASSETS / item["file"]
    mime = "image/svg+xml" if path.suffix == ".svg" else mimetypes.guess_type(path.name)[0]
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    parts.append(f'<div class="page"><img src="data:{mime};base64,{encoded}"></div>')
parts.append("</body></html>")
(ASSETS / "browser_render.html").write_text("\n".join(parts), encoding="utf-8")
print("Prepared", len(items), "local logo pages")
