"""
Optional Docling PDF ingestion experiment.

This script is intentionally outside the core runtime path. Docling is not listed
in requirements.txt because the submitted triage agent does not need it to run.

Use this when exploring how the original PDF assessment materials could be
converted into structured, auditable context for an LLM.

Optional setup:
    pip install docling

Run:
    python scripts/experimental/convert_assets_docling.py

Outputs:
    assets/converted_json/docling_raw/<pdf_name>.json
    assets/converted_json/llm_context/<pdf_name>.json
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sized
from pathlib import Path
from typing import Any

try:
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc.base import ImageRefMode
except ImportError as exc:
    print(
        "Docling is optional and is not installed. Install it manually with: pip install docling",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


ROOT_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT_DIR / "assets"
CONVERTED_DIR = ASSETS_DIR / "converted_json"
RAW_OUTPUT_DIR = CONVERTED_DIR / "docling_raw"
LLM_OUTPUT_DIR = CONVERTED_DIR / "llm_context"


def first_markdown_heading(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def split_markdown_sections(markdown: str) -> list[dict[str, Any]]:
    """Small, LLM-friendly section view derived from Docling markdown."""

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current is not None:
                current["content"] = current["content"].strip()
                sections.append(current)

            level = len(stripped) - len(stripped.lstrip("#"))
            current = {
                "heading": stripped.lstrip("#").strip(),
                "level": level,
                "content": "",
            }
            continue

        if current is None:
            current = {"heading": "Document", "level": 0, "content": ""}

        current["content"] += line + "\n"

    if current is not None:
        current["content"] = current["content"].strip()
        sections.append(current)

    return [section for section in sections if section["heading"] or section["content"]]


def export_plain_text(document: Any, markdown: str) -> str:
    if hasattr(document, "export_to_text"):
        return document.export_to_text()

    try:
        return document.export_to_markdown(strict_text=True)
    except TypeError:
        return markdown


def page_count(document: Any) -> int | None:
    num_pages = getattr(document, "num_pages", None)
    if callable(num_pages):
        value = num_pages()
        return value if isinstance(value, int) else None

    pages = getattr(document, "pages", None)
    if isinstance(pages, Sized):
        return len(pages)

    return None


def convert_pdf(converter: DocumentConverter, pdf_path: Path) -> None:
    result = converter.convert(pdf_path)
    document = result.document

    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LLM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem
    raw_path = RAW_OUTPUT_DIR / f"{stem}.json"
    compact_path = LLM_OUTPUT_DIR / f"{stem}.json"

    document.save_as_json(raw_path, image_mode=ImageRefMode.PLACEHOLDER)

    markdown = document.export_to_markdown()
    plain_text = export_plain_text(document, markdown)

    compact = {
        "source_file": pdf_path.name,
        "title": first_markdown_heading(markdown, fallback=stem.replace("_", " ")),
        "raw_docling_json": str(raw_path.relative_to(ROOT_DIR)),
        "page_count": page_count(document),
        "markdown": markdown,
        "plain_text": plain_text,
        "sections": split_markdown_sections(markdown),
    }

    compact_path.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Converted {pdf_path.name} -> {compact_path.relative_to(ROOT_DIR)}")


def main() -> None:
    pdf_paths = sorted(ASSETS_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDF files found in {ASSETS_DIR}")

    converter = DocumentConverter()
    for pdf_path in pdf_paths:
        convert_pdf(converter, pdf_path)


if __name__ == "__main__":
    main()
