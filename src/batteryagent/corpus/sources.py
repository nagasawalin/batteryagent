"""
corpus/sources.py — the literature register, corpus/sources.csv.

One row per paper: doc_id, title, year, doi, filename, core, serves.
`core` marks the papers system D loads in full; `serves` lists the question
ids a paper is meant to support. The register is committed; the PDFs are not.
"""

from __future__ import annotations

import pandas as pd

from ..config import path

COLUMNS = ("doc_id", "title", "year", "doi", "filename", "core", "serves")


def load_sources() -> pd.DataFrame:
    df = pd.read_csv(path("sources"), dtype=str).fillna("")
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"sources.csv lacks columns {missing}")
    df["core"] = df["core"].str.strip().str.lower().isin(["1", "true", "yes", "y"])
    if df.doc_id.duplicated().any():
        raise ValueError(f"duplicate doc_id: {sorted(df.doc_id[df.doc_id.duplicated()])}")
    return df.set_index("doc_id", drop=False)


def check_files(df: pd.DataFrame) -> dict[str, list[str]]:
    """Registered but absent, and present but unregistered."""
    papers = path("papers")
    on_disk = {p.name for p in papers.glob("*.pdf")}
    registered = set(df.filename)
    return {
        "missing_pdf": sorted(registered - on_disk),
        "unregistered_pdf": sorted(on_disk - registered),
    }


def coverage(df: pd.DataFrame) -> dict[str, list[str]]:
    """question id -> doc_ids that claim to serve it (from the `serves` column)."""
    out: dict[str, list[str]] = {}
    for doc_id, serves in zip(df.doc_id, df.serves):
        for qid in filter(None, (s.strip() for s in serves.replace(",", ";").split(";"))):
            out.setdefault(qid, []).append(doc_id)
    return out


if __name__ == "__main__":
    import json

    df = load_sources()
    print(f"{len(df)} registered, {int(df.core.sum())} core")
    print(json.dumps(check_files(df), indent=1))
    cov = coverage(df)
    thin = {q: d for q, d in cov.items() if len(d) < 2}
    print("questions served by fewer than 2 papers:", thin or "none")
