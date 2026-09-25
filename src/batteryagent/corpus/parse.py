"""
corpus/parse.py — PDF -> page-tagged blocks, one JSON file per paper.

    uv run python -m batteryagent.corpus.parse            # all registered PDFs
    uv run python -m batteryagent.corpus.parse --parser pymupdf --only attia2020

Output data/processed/parsed/<doc_id>.json:
    {"doc_id", "parser", "blocks": [{"kind", "page", "section", "text"}]}

kind is heading | text | table. Page numbers are kept on every block because
a citation is [doc_id, p. N]; without them no answer can be traced.

Docling is the default. PyMuPDF4LLM is the fallback, used automatically when
docling fails or returns suspiciously little text (typical of a scanned or
oddly encoded PDF). Everything from the reference list onward is dropped: a
bibliography matches almost every keyword query and would pollute retrieval.
"""

from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import path
from .sources import check_files, load_sources

STOP_SECTION = re.compile(
    r"^\W*(\d+(\.\d+)*\.?\s*)?(references|bibliography|acknowledge?ments?|"
    r"author contributions|competing interests|declaration of competing interest|"
    r"data availability|code availability)\b",
    re.I,
)
SKIP_LABELS = {"page_header", "page_footer", "picture", "document_index"}
MIN_CHARS = 5000  # below this a paper is almost certainly mis-parsed


# ------------------------------------------------------------------ docling
@lru_cache(maxsize=1)
def _docling_converter():
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def parse_docling(pdf: Path) -> list[dict]:
    doc = _docling_converter().convert(str(pdf)).document
    blocks, section = [], ""
    for item, _level in doc.iterate_items():
        label = getattr(item.label, "value", str(item.label))
        if label in SKIP_LABELS:
            continue
        prov = getattr(item, "prov", None)
        page = prov[0].page_no if prov else None

        if label in ("section_header", "title"):
            section = (item.text or "").strip()
            blocks.append({"kind": "heading", "page": page, "section": section,
                           "text": section})
            continue
        if label == "table":
            try:
                text = item.export_to_markdown(doc=doc)
            except TypeError:           # older docling signature
                text = item.export_to_markdown()
            kind = "table"
        else:
            text = getattr(item, "text", "") or ""
            kind = "text"
        text = text.strip()
        if text:
            blocks.append({"kind": kind, "page": page, "section": section, "text": text})
    return blocks


# ------------------------------------------------------------------ pymupdf4llm
_MD_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def parse_pymupdf(pdf: Path) -> list[dict]:
    import pymupdf4llm

    pages = pymupdf4llm.to_markdown(str(pdf), page_chunks=True, show_progress=False)
    blocks, section = [], ""
    for i, pg in enumerate(pages):
        page = pg.get("metadata", {}).get("page") or (i + 1)
        for para in re.split(r"\n\s*\n", pg.get("text", "")):
            para = para.strip()
            if not para:
                continue
            m = _MD_HEADING.match(para.splitlines()[0])
            if m and len(para.splitlines()) == 1:
                section = m.group(1).strip("* ").strip()
                blocks.append({"kind": "heading", "page": page, "section": section,
                               "text": section})
            elif para.startswith("|"):
                blocks.append({"kind": "table", "page": page, "section": section,
                               "text": para})
            else:
                blocks.append({"kind": "text", "page": page, "section": section,
                               "text": para})
    return blocks


# ------------------------------------------------------------------ common
# CHANGED 2026-09-25: cut_at_references used to truncate the whole paper at the
# first "References" heading after the first third, which drops a Methods
# section printed after the reference list (e.g. possibly severson2019, a core
# paper for system D). Now the stop section is skipped and inclusion resumes at
# a Methods/Experimental/Appendix heading. Check after parsing:
#   grep -c "C/50" data/processed/parsed/severson2019.json
# Nature-family papers print the main-text reference list BEFORE the Methods
# section. A heading like these ends a skipped stretch instead of the paper
# being truncated at the first "References".
RESUME_SECTION = re.compile(
    r"^\W*(\d+(\.\d+)*\.?\s*)?(online\s+)?(methods|materials and methods|"
    r"experimental( section| methods)?|appendix)\b",
    re.I,
)


def cut_at_references(blocks: list[dict]) -> tuple[list[dict], bool]:
    """Drop reference lists and back matter; keep a Methods section printed after them."""
    out, skipping, cut = [], False, False
    for i, b in enumerate(blocks):
        if b["kind"] == "heading":
            # never cut in the first third: some papers put "Data availability" early
            if STOP_SECTION.match(b["text"]) and i > len(blocks) / 3:
                skipping, cut = True, True
                continue
            if skipping and RESUME_SECTION.match(b["text"]):
                skipping = False
        if not skipping:
            out.append(b)
    return out, cut


def parse_one(pdf: Path, parser: str = "docling") -> tuple[list[dict], str]:
    used = parser
    try:
        blocks = parse_docling(pdf) if parser == "docling" else parse_pymupdf(pdf)
    except Exception as exc:  # noqa: BLE001
        print(f"  {parser} failed on {pdf.name}: {type(exc).__name__}: {exc}")
        blocks = []
    if parser == "docling" and sum(len(b["text"]) for b in blocks) < MIN_CHARS:
        print(f"  {pdf.name}: docling output too short, falling back to pymupdf4llm")
        blocks, used = parse_pymupdf(pdf), "pymupdf4llm"
    return blocks, used


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parser", choices=["docling", "pymupdf"], default="docling")
    ap.add_argument("--only", nargs="*", help="doc_ids to (re)parse")
    ap.add_argument("--force", action="store_true", help="re-parse existing outputs")
    a = ap.parse_args()

    df = load_sources()
    files = check_files(df)
    if files["missing_pdf"]:
        print("registered but missing:", files["missing_pdf"])
    if files["unregistered_pdf"]:
        print("on disk but not registered (ignored):", files["unregistered_pdf"])

    out_dir = path("parsed")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for doc_id, row in df.iterrows():
        if a.only and doc_id not in a.only:
            continue
        pdf = path("papers") / row.filename
        out = out_dir / f"{doc_id}.json"
        if not pdf.exists() or (out.exists() and not a.force):
            continue
        print(f"parsing {doc_id}")
        blocks, used = parse_one(pdf, a.parser)
        blocks, cut = cut_at_references(blocks)
        out.write_text(json.dumps({"doc_id": doc_id, "parser": used, "blocks": blocks},
                                  ensure_ascii=False))
        chars = sum(len(b["text"]) for b in blocks)
        report.append({"doc_id": doc_id, "parser": used, "blocks": len(blocks),
                       "chars": chars,
                       "pages": len({b["page"] for b in blocks if b["page"]}),
                       "tables": sum(b["kind"] == "table" for b in blocks),
                       "refs_cut": cut, "suspect": chars < MIN_CHARS or not cut})

    if report:
        rep = pd.DataFrame(report)
        rep.to_csv(path("results") / "parse_report.csv", index=False)
        print(rep.to_string(index=False))
        print("\nsuspect = too little text, or no reference section found: open those "
              "PDFs and the JSON side by side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
