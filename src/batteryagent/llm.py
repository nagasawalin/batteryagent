"""
batteryagent/llm.py — thin wrapper around the Anthropic Messages API.

Retries transient failures, and extracts text and token usage in one place so
every system logs usage the same way.

CHANGED 2026-09-25: anthropic SDK 1.x (installed: pyproject pins >=1.2.0)
removed `temperature`, `top_p` and `top_k` from messages.create(); passing
temperature= raises TypeError before any request is sent. The SDK's migration
notes route sampling parameters through `extra_body`, which is merged into the
JSON request. So temperature from config.yaml now travels in extra_body.

Whether a given MODEL still accepts temperature is a separate question: third-
party reports (Sep 2026, not verified here) say the API returns HTTP 400
"`temperature` is deprecated for this model" for claude-sonnet-5 while still
accepting it for claude-haiku-4-5. That case is NOT silently dropped here,
because temperature 0 is an experimental control: create() raises
TemperatureRejected, and the decision is made explicitly in config.yaml.
"""

from __future__ import annotations

import time
from functools import lru_cache

from .config import ROOT, cfg

RETRY_STATUS = {429, 500, 502, 503, 529}


class TemperatureRejected(RuntimeError):
    """The API refused the temperature parameter for this model."""


@lru_cache(maxsize=1)
def client():
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return anthropic.Anthropic()


def create(**kwargs):
    """messages.create with exponential backoff on rate limits and overload.

    temperature is taken from config unless given, so all systems share it,
    and is sent through extra_body (see module docstring).
    """
    import anthropic

    kwargs.setdefault("model", cfg()["models"]["system"])
    kwargs.setdefault("max_tokens", cfg()["models"]["max_tokens"])
    t = kwargs.pop("temperature", cfg()["models"].get("temperature"))
    if t is not None:
        kwargs["extra_body"] = {**kwargs.get("extra_body", {}), "temperature": t}

    for attempt in range(6):
        try:
            return client().messages.create(**kwargs)
        except anthropic.APIConnectionError:
            pass
        except anthropic.APIStatusError as e:
            if e.status_code == 400 and "temperature" in str(e).lower():
                raise TemperatureRejected(
                    f"model {kwargs['model']!r} rejects temperature={t}: {e}. "
                    "Decide in config.yaml (models.temperature: null, or another model)."
                ) from e
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
