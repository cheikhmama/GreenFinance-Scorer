"""Download public technology marks and keep their provenance outside the PDF."""
from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "technology_logos_assets"
ASSETS.mkdir(exist_ok=True)


def get(url):
    response = requests.get(url, timeout=35, headers={"User-Agent": "GreenFinance-Scorer-PFE-assets"})
    response.raise_for_status()
    return response


def catalogs():
    entries = {
        "devicon": "https://api.github.com/repos/devicons/devicon/git/trees/master?recursive=1",
        "logos": "https://api.github.com/repos/gilbarbara/logos/git/trees/main?recursive=1",
        "simpleicons": "https://api.github.com/repos/simple-icons/simple-icons/git/trees/develop?recursive=1",
    }
    for key, url in entries.items():
        path = ASSETS / f"catalog_{key}.json"
        if not path.exists():
            path.write_bytes(get(url).content)
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "tree" in data:
            items = [x["path"] for x in data["tree"] if x["path"].endswith(".svg")]
            match = [x for x in items if any(w in x.lower() for w in
                     ["react", "fastapi", "pydantic", "sql", "uv", "ruff", "pytest", "biome",
                      "paddle", "gemini", "hugging", "numpy", "pytorch", "zod", "radix", "orval",
                      "tanstack", "lucide", "shadcn", "hatch", "mypy", "httpx", "draw", "diagrams",
                      "testing", "cva", "yaml", "json", "jwt", "google-font", "powershell", "openapi"])]
            print(key, json.dumps(match))
        else:
            print(key, "catalog saved")


def download_manifest():
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))

    def one(item):
        path = ASSETS / item["file"]
        if path.exists() and path.stat().st_size > 40:
            return item["name"], "cached", path.stat().st_size
        errors = []
        for url in item["urls"]:
            try:
                response = get(url)
                content = response.content
                if len(content) < 40 or b"<!DOCTYPE html" in content[:100] or b"<html" in content[:100]:
                    raise ValueError("Response is not a usable logo asset")
                path.write_bytes(content)
                item["source_url"] = url
                return item["name"], "downloaded", len(content)
            except Exception as exc:
                errors.append(str(exc)[:170])
        item["error"] = errors
        return item["name"], "FAILED", errors

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for result in executor.map(one, manifest):
            print(json.dumps(result, ensure_ascii=True), flush=True)
    (ASSETS / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if "--catalogs" in sys.argv:
        catalogs()
    else:
        download_manifest()
