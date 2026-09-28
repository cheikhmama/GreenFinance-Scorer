"""Choose genuine marks for the technologies retained by the repository audit."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "technology_logos_assets"
catalogs = {
    key: {x["path"] for x in json.loads((ASSETS / f"catalog_{key}.json").read_text(encoding="utf-8"))["tree"]}
    for key in ["logos", "devicon", "simpleicons"]
}
items = []


def raw(name, group, url, ext="svg", alternatives=()):
    file = "".join(c if c.isalnum() else "_" for c in name.lower()) + "." + ext
    items.append({"name": name, "group": group, "file": file, "urls": [url, *alternatives]})


def dev(name, group, slug, variant="original-wordmark"):
    path = f"icons/{slug}/{slug}-{variant}.svg"
    assert path in catalogs["devicon"], path
    raw(name, group, "https://raw.githubusercontent.com/devicons/devicon/master/" + path)


def logo(name, group, slug):
    path = f"logos/{slug}.svg"
    assert path in catalogs["logos"], path
    raw(name, group, "https://raw.githubusercontent.com/gilbarbara/logos/main/" + path)


def simple(name, group, slug):
    path = f"icons/{slug}.svg"
    assert path in catalogs["simpleicons"], path
    raw(name, group, "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/" + path)


dev("React", "frontend", "react")
dev("TypeScript", "frontend", "typescript", "original")
dev("Vite", "frontend", "vite", "original")
items[-1]["file"] = "vite_symbol.svg"
dev("Tailwind CSS", "frontend", "tailwindcss", "original")
items[-1]["file"] = "tailwind_css_symbol.svg"
simple("shadcn ui", "frontend", "shadcnui")
simple("Radix UI", "frontend", "radixui")
simple("Lucide", "frontend", "lucide")
logo("TanStack React Query", "frontend", "react-query")
dev("React Router", "frontend", "reactrouter")
simple("React Hook Form", "frontend", "reacthookform")
logo("Zod", "frontend", "zod")
raw("Orval", "frontend", "https://orval.dev/images/emblem.svg")
raw("tailwind-merge", "frontend", "https://raw.githubusercontent.com/dcastil/tailwind-merge/v3.6.0/assets/logo.svg")
simple("Google Fonts", "frontend", "googlefonts")
dev("HTML", "frontend", "html5")
logo("CSS", "frontend", "css")
logo("SVG", "frontend", "svg")

dev("Python", "backend", "python")
logo("FastAPI", "backend", "fastapi")
raw("Uvicorn", "backend", "https://raw.githubusercontent.com/tomchristie/uvicorn/main/docs/uvicorn.png", "png")
raw("Starlette", "backend", "https://raw.githubusercontent.com/Kludex/starlette/main/docs/img/starlette.svg")
simple("Pydantic", "backend", "pydantic")
raw("structlog", "backend", "https://www.structlog.org/en/stable/_static/structlog_logo.svg")
dev("PostgreSQL", "backend", "postgresql")
raw("SQLModel", "backend", "https://sqlmodel.tiangolo.com/img/logo-margin/logo-margin-vector.svg")
dev("SQLAlchemy", "backend", "sqlalchemy")
raw("Psycopg", "backend", "https://www.psycopg.org/img/logo.png", "png")
dev("Redis", "backend", "redis")
logo("JWT", "backend", "jwt")

raw("Docling", "ai", "https://raw.githubusercontent.com/docling-project/docling/main/docs/assets/logo.png", "png")
raw("RapidOCR", "ai", "https://github.com/RapidAI/RapidOCR/releases/download/v1.1.0/Logov2_white.png", "png")
simple("PaddlePaddle", "ai", "paddlepaddle")
raw("PyMuPDF", "ai", "https://pymupdf.pro/images/py-mupdf-github-icon.png", "png")
raw("BGE FlagEmbedding", "ai", "https://raw.githubusercontent.com/FlagOpen/FlagEmbedding/master/imgs/bge_logo.jpg", "jpg")
items[-1]["exclude"] = "Promotional illustration rather than a standalone logo"
dev("NumPy", "ai", "numpy")
logo("PyTorch", "ai", "pytorch")
logo("Transformers Hugging Face", "ai", "hugging-face")
raw("Sentence Transformers", "ai", "https://raw.githubusercontent.com/huggingface/sentence-transformers/main/docs/img/logo.png", "png")
logo("Gemini", "ai", "google-gemini")
logo("YAML", "ai", "yaml")

logo("Docker", "tools", "docker")
dev("Linux", "tools", "linux", "original")
dev("Ubuntu", "tools", "ubuntu")
simple("uv", "tools", "uv")
raw("Hatch", "tools", "https://raw.githubusercontent.com/pypa/hatch/master/docs/assets/images/logo.svg")
logo("Node js", "tools", "nodejs")
logo("npm", "tools", "npm")
logo("Git", "tools", "git")
dev("GitHub", "tools", "github")
dev("GitHub Actions", "tools", "githubactions", "original")
logo("Bash", "tools", "bash-icon")
items[-1]["file"] = "bash_symbol.svg"
dev("PowerShell", "tools", "powershell", "original")

simple("Ruff", "validation", "ruff")
raw("mypy", "validation", "https://raw.githubusercontent.com/python/mypy/master/docs/source/mypy_light.svg")
logo("Biome", "validation", "biomejs")
dev("pytest", "validation", "pytest")
raw("HTTPX", "validation", "https://raw.githubusercontent.com/encode/httpx/master/docs/img/butterfly.png", "png")
raw("coverage py", "validation", "https://raw.githubusercontent.com/coveragepy/coveragepy/main/doc/media/sleepy-snake-circle-150.png", "png")
logo("Vitest", "validation", "vitest")
logo("Testing Library", "validation", "testing-library")
logo("Markdown", "validation", "markdown")
logo("OpenAPI", "validation", "openapi")
simple("diagrams net", "validation", "diagramsdotnet")

(ASSETS / "manifest.json").write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Prepared {len(items)} logo entries")
