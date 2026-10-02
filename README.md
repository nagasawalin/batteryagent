# BatteryAgent

An LLM agent for battery degradation diagnostics, and a controlled comparison
of four ways to give a language model the information it needs.

DTU special course, autumn 2026. Author: Zhenlin Xie.

## What this project does

The questions are about the fast-charging dataset of Severson et al. (2019),
batch 1: 46 LFP/graphite cells that differ mainly in their charging policy.
Answering them can need the cell's own measurements, the published
literature, or both.

Four systems answer the same questions with the same model
(`claude-sonnet-4-6`, temperature 0) and almost the same prompt. Only the
information they can reach differs:

| System | Information available |
|---|---|
| A, plain LLM | the question only |
| B, single-shot RAG | five passages retrieved once with the question |
| C, BatteryAgent | a tool-calling loop with three tools: cell specification, cell data, literature search |
| D, long context | the full text of five core papers, no search |

System C is a hand-written loop of about 100 lines (`src/batteryagent/agent/loop.py`),
not an agent framework. Its literature tool uses the same retriever as system B
(BGE-M3 dense + BM25, fused by RRF, reranked by bge-reranker-v2-m3).

## Main results (20 test questions)

| System | Must-include coverage | Must-not violations | Supported citations | Input tokens / question | Time / question (s) |
|---|---|---|---|---|---|
| A | 0.32 | 1/6 | 0/0 | 178 | 8.8 |
| B | 0.30 | 1/6 | 28/28 | 2,932 | 34.4 |
| C | 0.83 | 0/6 | 49/49 | 16,303 | 44.2 |
| D | 0.33 | 1/6 | 62/62 | 91,163 | 8.7 |

Coverage is the share of required points an answer met, checked by an LLM judge
whose decisions are verified against verbatim quotes. C had higher coverage than
each baseline on 13 or 14 of the 20 questions and lower on none (sign test,
p ≤ 0.00024). Most of the gain comes from access to the measurement data; on
literature-only questions C was not clearly better.

## Repository layout

```
config.yaml                 every path, model name and threshold
corpus/sources.csv          the 27 papers of the corpus (doc_id, DOI, title)
eval/questions.jsonl        30 questions with reference answers (10 dev, 20 test)
eval/retrieval_queries.jsonl, eval/qrels.jsonl   retrieval evaluation set
src/batteryagent/
  data/        Severson loader (severson.py) and derived quantities (features.py)
  corpus/      PDF parsing, chunking, embedding
  retrieval/   BM25, dense, RRF fusion, reranker
  tools/       get_cell_spec, get_cell_data, search_literature
  agent/       the tool loop, prompts, traces
  eval/        baselines A/B/D, test runs, LLM judge, citation check, reports
scripts/       data inventory, question set, bibliography, sign test, figure
results/       result tables of the final run and the retrieval ablation
```

## Not included

The data and the papers are not redistributed here:

- **Battery data.** Download the batch 1 file
  `2017-05-12_batchdata_updated_struct_errorcorrect.mat` (about 3 GB) of
  Severson et al. from https://data.matr.io/1/ and put it in `data/raw/`.
- **Papers.** The DOIs are in `corpus/sources.csv`. Save each PDF as
  `data/raw/papers/<doc_id>.pdf`.
- **Traces** of the test run are not committed (they contain long passages of
  the papers).

## How to run

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Put your API key in
`.env`:

```
ANTHROPIC_API_KEY=...
```

```bash
uv sync

# 1. battery data -> data/processed/{cells,summary}.parquet
uv run python scripts/inventory_severson.py data/raw/2017-05-12_batchdata_updated_struct_errorcorrect.mat

# 2. literature corpus
uv run python -m batteryagent.corpus.parse
uv run python -m batteryagent.corpus.chunk
uv run python -m batteryagent.corpus.embed

# 3. try it
uv run python -m batteryagent ask "Why does cell b1c20 reach end of life earlier than b1c5?"
uv run python -m batteryagent tool get_cell_data '{"cell_id": "b1c6"}'

# 4. retrieval ablation
uv run python -m batteryagent.eval.retrieval_ablation --variants dense bm25 hybrid hybrid_rerank

# 5. test run, judge and tables
uv run python -m batteryagent.eval.run_eval --split test --run-id test-final
uv run python -m batteryagent.eval.judge --run-id test-final
uv run python -m batteryagent.eval.citations --run-id test-final
uv run python -m batteryagent.eval.report --run-id test-final
uv run python scripts/sign_test.py results/runs/test-final/judgements.jsonl
```

`eval/questions.jsonl` is committed and frozen (tag `refs-v0.2`). Do not
regenerate it with `scripts/build_questions.py` if you want to reproduce the
reported numbers. The code used for the reported test run is tagged
`test-freeze` (commit `02700c6`). Outputs of a rerun will differ slightly,
since a model at temperature 0 is not fully deterministic.

## Data source

K. A. Severson et al., "Data-driven prediction of battery cycle life before
capacity degradation", *Nature Energy* 4, 383–391 (2019).
