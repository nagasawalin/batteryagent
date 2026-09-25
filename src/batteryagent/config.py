"""
batteryagent/config.py — the single place paths and settings are read from.

Paths are resolved against the repository root, found by walking up from this
file, so every module works regardless of the current working directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


def _find_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "config.yaml").exists() and (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


ROOT = _find_root()


@lru_cache(maxsize=1)
def cfg() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def path(key: str) -> Path:
    """Absolute path for a key under `paths:` in config.yaml."""
    return ROOT / cfg()["paths"][key]
