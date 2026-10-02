"""
make_bib.py — build document.bib for the report.

    cd ~/batteryagent
    uv run python scripts/make_bib.py

Reads corpus/sources.csv, asks doi.org for the BibTeX of every DOI, renames
each entry key to the doc_id (so \\cite{severson2019} works), adds the five
entries that are not in the corpus, and writes document.bib in the current
folder. Upload that file to Overleaf and replace the old one.

Only the standard library is used. Needs internet (doi.org).
"""

from __future__ import annotations

import csv
import re
import time
import urllib.request
from pathlib import Path

SOURCES = Path("corpus/sources.csv")
OUT = Path("document.bib")

# Entries that are not corpus papers. Check the four CS entries once against
# arXiv / the proceedings page before submitting.
EXTRA = r"""
@misc{severson2019code,
  title        = {data-driven-prediction-of-battery-cycle-life-before-capacity-degradation},
  howpublished = {GitHub repository, \url{https://github.com/rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation}},
  note         = {Accessed: 2026-09-25}
}

@inproceedings{zheng2023judging,
  author    = {Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and Zhuang, Siyuan and Wu, Zhanghao and Zhuang, Yonghao and Lin, Zi and Li, Zhuohan and Li, Dacheng and Xing, Eric P. and Zhang, Hao and Gonzalez, Joseph E. and Stoica, Ion},
  title     = {Judging {LLM}-as-a-Judge with {MT-Bench} and {Chatbot Arena}},
  booktitle = {Advances in Neural Information Processing Systems 36, Datasets and Benchmarks Track},
  year      = {2023}
}

@inproceedings{panickssery2024llm,
  author    = {Panickssery, Arjun and Bowman, Samuel R. and Feng, Shi},
  title     = {{LLM} Evaluators Recognize and Favor Their Own Generations},
  booktitle = {Advances in Neural Information Processing Systems 37},
  year      = {2024}
}

@inproceedings{lewis2020rag,
  author    = {Lewis, Patrick and Perez, Ethan and Piktus, Aleksandra and Petroni, Fabio and Karpukhin, Vladimir and Goyal, Naman and K{\"u}ttler, Heinrich and Lewis, Mike and Yih, Wen-tau and Rockt{\"a}schel, Tim and Riedel, Sebastian and Kiela, Douwe},
  title     = {Retrieval-Augmented Generation for Knowledge-Intensive {NLP} Tasks},
  booktitle = {Advances in Neural Information Processing Systems 33},
  year      = {2020}
}

@inproceedings{yao2023react,
  author    = {Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and Du, Nan and Shafran, Izhak and Narasimhan, Karthik and Cao, Yuan},
  title     = {{ReAct}: Synergizing Reasoning and Acting in Language Models},
  booktitle = {International Conference on Learning Representations},
  year      = {2023}
}
"""


def fetch_bibtex(doi: str) -> str:
    req = urllib.request.Request(f"https://doi.org/{doi}",
                                 headers={"Accept": "application/x-bibtex; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def rekey(bib: str, key: str) -> str:
    """'@article{Severson_2019, ...' -> '@article{severson2019, ...'"""
    return re.sub(r"^\s*@(\w+)\{[^,]*,", lambda m: f"@{m.group(1)}{{{key},", bib, count=1)


def main() -> int:
    rows = list(csv.DictReader(SOURCES.open(encoding="utf-8")))
    entries, failed = [], []
    for row in rows:
        key, doi = row["doc_id"], row["doi"].strip()
        try:
            entries.append(rekey(fetch_bibtex(doi).strip(), key))
            print(f"ok      {key}")
        except Exception as exc:  # noqa: BLE001
            failed.append((key, doi))
            print(f"FAILED  {key}  {doi}  ({type(exc).__name__}: {exc})")
        time.sleep(0.5)  # be polite to doi.org

    OUT.write_text("\n\n".join(entries) + "\n" + EXTRA, encoding="utf-8")
    print(f"\nwrote {OUT}: {len(entries)} corpus entries + 5 extra")
    if failed:
        print("add these by hand (e.g. doi2bib.org), key = doc_id:")
        for key, doi in failed:
            print(f"  {key}  https://doi.org/{doi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
