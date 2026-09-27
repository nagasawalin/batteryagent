"""
scripts/register_papers.py — rename the downloaded PDFs to <doc_id>.pdf and
write corpus/sources.csv.

    uv run python scripts/register_papers.py

Provenance of every column, so nothing here is typed from memory:
  doi      read from page 1-2 of each PDF (2026-09-25); attia2022, whose PDF
           yields none, and waldmann2015, added later, checked against
           publisher/repository records
  filename None = downloaded name unknown: the script finds the PDF whose
           first two pages contain the DOI
  title    Crossref, looked up by DOI at run time (HTML tags stripped)
  year     Crossref: published-print if present, else issued (volume year)
  doc_id   <first author><year>[a|b], lowercase ASCII — must match [A-Za-z0-9_-]
           because judge.py parses citations [doc_id, p. N] with that pattern
  core     1 = full text given to system D
  serves   question ids the paper is meant to support (current ids, mapped from
           titles, not from reading the full text)

Safe to re-run: files already renamed are left alone; the CSV is rewritten.
PDFs are not in git (data/ is ignored); corpus/sources.csv is.
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "data" / "raw" / "papers"
OUT = ROOT / "corpus" / "sources.csv"

# downloaded filename -> doc_id, doi, core, serves
REGISTER = [
    ("1-s2.0-S0013468605007899-main.pdf", "troltzsch2006", "10.1016/j.electacta.2005.02.148", 0, "M3"),
    ("1-s2.0-S0378775303001903-main.pdf", "wright2003", "10.1016/S0378-7753(03)00190-3", 0, "M3"),
    ("1-s2.0-S0378775304008146-main.pdf", "bloom2005", "10.1016/j.jpowsour.2004.07.021", 0, "M5"),
    ("1-s2.0-S0378775305000832-main.pdf", "vetter2005", "10.1016/j.jpowsour.2005.01.006", 0, "M1;M3;T4"),
    ("1-s2.0-S0378775312011330-main.pdf", "dubarry2012", "10.1016/j.jpowsour.2012.07.016", 1, "M5"),
    ("1-s2.0-S0378775313014584-main.pdf", "baumhofer2014", "10.1016/j.jpowsour.2013.08.108", 0, "C2;C1"),
    ("1-s2.0-S0378775315301555-main.pdf", "schuster2015b", "10.1016/j.jpowsour.2015.08.001", 0, "C2"),
    ("1-s2.0-S0378775316305249-main.pdf", "ansean2016", "10.1016/j.jpowsour.2016.04.140", 0, "M1;M4;C1"),
    ("1-s2.0-S0378775316316998-main.pdf", "birkl2017", "10.1016/j.jpowsour.2016.12.011", 1, "M5;M1"),
    ("1-s2.0-S0378775316317864-main.pdf", "harris2017", "10.1016/j.jpowsour.2016.12.083", 0, "C2"),
    ("1-s2.0-S037877531730143X-main.pdf", "lewerenz2017a", "10.1016/j.jpowsour.2017.01.133", 0, "M2"),
    ("1-s2.0-S0378775317305670-main.pdf", "ansean2017", "10.1016/j.jpowsour.2017.04.072", 0, "M1;M4"),
    ("1-s2.0-S0378775317307619-main.pdf", "yang2017", "10.1016/j.jpowsour.2017.05.110", 0, "M1"),
    ("1-s2.0-S0378775317308388-main.pdf", "ahmed2017", "10.1016/j.jpowsour.2017.06.055", 0, "M4;C1"),
    ("1-s2.0-S0378775317312788-main.pdf", "lewerenz2017b", "10.1016/j.jpowsour.2017.09.059", 0, "M5"),
    # dropped 2026-09-25, garbled text after re-parse: ("1-s2.0-S2352152X15000092-main.pdf", "schuster2015a", "10.1016/j.est.2015.05.003", 0, "M1;C2"),
    ("6079702358aebb8e9ea0250d.pdf", "edge2021", "10.1039/d1cp00359c", 1, "T4;T6;C6;M1;M5"),
    ("Attia_2022_J._Electrochem._Soc._169_060517.pdf", "attia2022", "10.1149/1945-7111/ac6d13", 1, "M1"),
    ("Gyenes_2015_J._Electrochem._Soc._162_A278.pdf", "gyenes2015", "10.1149/2.0191503jes", 0, "M2"),
    ("Liu_2010_J._Electrochem._Soc._157_A499.pdf", "liu2010", "10.1149/1.3294790", 0, "M1;M3"),
    ("Pinson_2013_J._Electrochem._Soc._160_A243.pdf", "pinson2013", "10.1149/2.044302jes", 0, "M1;M3"),
    ("Preger_2020_J._Electrochem._Soc._167_120532.pdf", "preger2020", "10.1149/1945-7111/abae37", 0, "T6;T4;C6"),
    ("Safari_2011_J._Electrochem._Soc._158_A1123.pdf", "safari2011", "10.1149/1.3614529", 0, "M1;M3"),
    ("Severson et al. - 2019 - Data-driven prediction of battery cycle life before capacity degradation.pdf",
     "severson2019", "10.1038/s41560-019-0356-8", 1, "M6;M2;C1"),
    ("Smith_2011_Electrochem._Solid-State_Lett._14_A39.pdf", "smith2011", "10.1149/1.3543569", 0, "M5"),
    ("Waldmann_2014_J._Electrochem._Soc._161_A1742.pdf", "waldmann2014", "10.1149/2.1001410jes", 0, "M3"),
    ("jp510071d.pdf", "sarasketa2015", "10.1021/jp510071d", 0, "M5;M1"),
    # added 2026-09-25; file name as downloaded not known -> located by DOI
    (None, "waldmann2015", "10.1149/2.0561506jes", 0, "C6;T4"),
]
DOC_ID = re.compile(r"^[a-z0-9_-]+$")


def crossref(doi: str) -> tuple[str, str]:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    req = urllib.request.Request(url, headers={"User-Agent": "batteryagent-course-project/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        m = json.load(r)["message"]
    title = re.sub(r"<[^>]+>", "", (m.get("title") or [""])[0])
    title = re.sub(r"\s+", " ", title).strip()
    date = (m.get("published-print") or m.get("issued") or {}).get("date-parts", [[None]])[0][0]
    return title, str(date or "")


def find_by_doi(doi: str) -> str | None:
    """Name of an unregistered PDF whose first two pages contain `doi`."""
    import pymupdf

    taken = {f for f, *_ in REGISTER if f} | {f"{r[1]}.pdf" for r in REGISTER}
    for p in sorted(PAPERS.glob("*.[pP][dD][fF]")):
        if p.name in taken:
            continue
        d = pymupdf.open(p)
        text = " ".join(d[i].get_text() for i in range(min(2, len(d)))).lower()
        if doi.lower() in text:
            return p.name
    return None


def main() -> int:
    problems, rows = [], []
    for fname, doc_id, doi, core, serves in REGISTER:
        assert DOC_ID.match(doc_id), doc_id
        dst = PAPERS / f"{doc_id}.pdf"
        if fname is None and not dst.exists():
            fname = find_by_doi(doi)
            if fname is None:
                problems.append(f"no PDF contains {doi} ({doc_id}); rename it by hand "
                                f"to {doc_id}.pdf and re-run")
                fname = f"{doc_id}.pdf"
        src = PAPERS / (fname or f"{doc_id}.pdf")
        if src.exists() and not dst.exists():
            src.rename(dst)
        elif not dst.exists():
            problems.append(f"PDF missing for {doc_id}: {fname}")
        try:
            title, year = crossref(doi)
        except Exception as exc:  # noqa: BLE001
            title, year = "", ""
            problems.append(f"Crossref failed for {doc_id} ({doi}): {exc}")
        m = re.search(r"(\d{4})[ab]?$", doc_id)
        if year and m and m.group(1) != year:
            problems.append(f"year mismatch {doc_id}: Crossref says {year}")
        rows.append({"doc_id": doc_id, "title": title, "year": year, "doi": doi,
                     "filename": f"{doc_id}.pdf", "core": core, "serves": serves})
        time.sleep(0.3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    known = {r["doc_id"] for r in rows}
    leftover = sorted(p.name for p in PAPERS.glob("*.pdf") if p.stem not in known)
    for r in rows:
        print(f"{r['doc_id']:14s} {r['year']:5s} core={r['core']} {r['serves']:16s} {r['title'][:70]}")
    print(f"\n{len(rows)} rows -> {OUT}")
    print("leftover PDFs not registered:", leftover or "none")
    print("problems:", *(problems or ["none"]), sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
