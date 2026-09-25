"""
batteryagent/llm.py — thin wrapper around the Anthropic Messages API.

Retries transient failures, and extracts text and token usage in one place so
every system logs usage the same way.
"""

from __future__ import annotations

import time
from functools import lru_cache

from .config import ROOT, cfg

RETRY_STATUS = {429, 500, 502, 503, 529}


@lru_cache(maxsize=1)
def client():
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return anthropic.Anthropic()


def create(**kwargs):
    """messages.create with exponential backoff on rate limits and overload.

    temperature is taken from config unless given, so all systems share it.
    """
    import anthropic

    kwargs.setdefault("model", cfg()["models"]["system"])
    kwargs.setdefault("max_tokens", cfg()["models"]["max_tokens"])
    t = cfg()["models"].get("temperature")
    if t is not None:
        kwargs.setdefault("temperature", t)

    for attempt in range(6):
        try:
            return client().messages.create(**kwargs)
        except anthropic.APIConnectionError:
            pass
        except anthropic.APIStatusError as e:
            if e.status_code not in RETRY_STATUS:
                raise
        time.sleep(min(60, 2 ** attempt * 2))
    raise RuntimeError("LLM call failed after 6 attempts")


def text_of(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def usage_of(resp) -> dict:
    u = resp.usage
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
