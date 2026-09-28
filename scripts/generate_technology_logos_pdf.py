"""Compose an image-only PDF from sourced logo assets; provenance is a sidecar."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "technology_logos_assets"
OUT = ROOT / "docs" / "GreenFinance_Scorer_Logos_Technologies.pdf"
PREVIEW = ROOT / "docs" / "technology_logos_preview"
PREVIEW.mkdir(exist_ok=True)


def load_logo(item, index, rendered):
    path = ASSETS / item["file"]
    pdf = pymupdf.open()
    pdf.insert_pdf(rendered, from_page=index, to_page=index)
    page = pdf[0]
    scale = min(3, 1000 / max(page.rect.width, page.rect.height))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    delta = ImageChops.difference(image, Image.new("RGB", image.size, "white")).convert("L")
    # Find the visible artwork, retaining its actual colors and geometry.
    bounds = delta.point(lambda p: 255 if p > 15 else 0).getbbox()
    if not bounds:
        raise ValueError(f"Empty artwork: {item['name']}")
    clip = pymupdf.Rect(*[v / scale for v in bounds])
    clip += (-2 / scale, -2 / scale, 2 / scale, 2 / scale)
    clip &= page.rect
    if item.get("clip"):
        clip = pymupdf.Rect(item["clip"])
    return pdf, clip


def review_sheet(manifest, loaded):
    cell_w, cell_h = 236, 150
    cols = 5
    rows = math.ceil(len(manifest) / cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#EBEFED")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", 14)
    for i, item in enumerate(manifest):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        draw.rectangle((x + 5, y + 5, x + cell_w - 5, y + 120), fill="white")
        if item["name"] in loaded:
            pdf, clip = loaded[item["name"]]
            tmp = pymupdf.open()
            p = tmp.new_page(width=220, height=108)
            p.show_pdf_page(pymupdf.Rect(8, 8, 212, 100), pdf, 0, clip=clip)
            pix = p.get_pixmap(alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            sheet.paste(im, (x + 8, y + 8))
            tmp.close()
        draw.text((x + 8, y + 125), item["name"], fill="#18354A", font=font)
    sheet.save(PREVIEW / "asset_review.jpg", quality=94)


def create_pdf(manifest, loaded):
    doc = pymupdf.open()
    pages = []
    # Keep families together. The first family occupies two balanced sheets.
    for group in ["frontend", "backend", "ai", "tools", "validation"]:
        entries = [i for i in manifest if i["group"] == group and i["name"] in loaded and not i.get("exclude")]
        count_pages = math.ceil(len(entries) / 12)
        per_page = math.ceil(len(entries) / count_pages)
        pages.extend(entries[i:i + per_page] for i in range(0, len(entries), per_page))
    positions = []
    for page_no, entries in enumerate(pages):
        page = doc.new_page(width=595.276, height=841.89)
        cols = 3
        rows = math.ceil(len(entries) / cols)
        cell_w, cell_h = 165.76, 176
        x_start = (page.rect.width - cols * cell_w) / 2
        y_start = (page.rect.height - rows * cell_h) / 2
        for j, item in enumerate(entries):
            row, col = divmod(j, cols)
            last_count = len(entries) - row * cols
            centering = (cols - last_count) * cell_w / 2 if last_count < cols else 0
            x = x_start + col * cell_w + centering
            y = y_start + row * cell_h
            pdf, clip = loaded[item["name"]]
            ratio = clip.width / clip.height
            if ratio >= 2.0:
                w, h = 144, 66
            elif ratio >= 1.2:
                w, h = 129, 89
            else:
                w, h = 99, 105
            if item.get("scale"):
                w *= item["scale"]
                h *= item["scale"]
            rect = pymupdf.Rect(x + (cell_w - w) / 2, y + (cell_h - h) / 2,
                                x + (cell_w + w) / 2, y + (cell_h + h) / 2)
            page.show_pdf_page(rect, pdf, 0, clip=clip, keep_proportion=True)
            positions.append({"name": item["name"], "page": page_no + 1, "rect": list(rect)})
    doc.set_metadata({"title": "GreenFinance-Scorer — Logos des technologies",
                      "author": "GreenFinance-Scorer", "subject": "Logos uniquement"})
    doc.save(OUT, garbage=4, deflate=True)
    page_thumbs = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False)
        path = PREVIEW / f"page_{i+1:02d}.png"
        pix.save(path)
        im = Image.open(path).convert("RGB")
        im.thumbnail((298, 421))
        page_thumbs.append(im)
    sheet = Image.new("RGB", (3 * 318 + 20, math.ceil(len(page_thumbs) / 3) * 441 + 20), "#E7ECE9")
    for i, im in enumerate(page_thumbs):
        sheet.paste(im, (20 + (i % 3) * 318, 20 + (i // 3) * 441))
    sheet.save(PREVIEW / "pages_contact.jpg", quality=95)
    report = {"pages": len(doc), "logos": len(positions), "placements": positions,
              "text_characters_per_page": [len(p.get_text().strip()) for p in doc],
              "failed_assets": [i["name"] for i in manifest if i["name"] not in loaded],
              "pdf_bytes": OUT.stat().st_size}
    (PREVIEW / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "placements"}, indent=2))


if __name__ == "__main__":
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    rendered = pymupdf.open(ASSETS / "browser_render.pdf")
    assert len(rendered) == len(manifest), "The browser render must contain one page per source logo"
    loaded = {}
    for i, item in enumerate(manifest):
        try:
            loaded[item["name"]] = load_logo(item, i, rendered)
        except Exception as exc:
            print(f"Asset failure {item['name']}: {exc}")
    review_sheet(manifest, loaded)
    create_pdf(manifest, loaded)
