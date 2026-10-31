"""The only place that talks to the LLM provider (Anthropic Messages API over HTTP).

Every function raises LLMUnavailable when no key is configured or the call fails after one retry;
callers then switch to the deterministic fallback (spec E4/E5).
"""
import json
import re
import time

import httpx

from config.settings import settings

TIMEOUT_S = 20


class LLMUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(settings.llm_api_key)


def messages(system: str, msgs: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024) -> dict:
    if not enabled():
        raise LLMUnavailable("no key")
    body = {"model": settings.llm_model, "max_tokens": max_tokens, "system": system, "messages": msgs}
    if tools:
        body["tools"] = tools
    headers = {"x-api-key": settings.llm_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    last = None
    for attempt in range(2):
        try:
            r = httpx.post(f"{settings.llm_base_url}/v1/messages", json=body, headers=headers, timeout=TIMEOUT_S)
            if 400 <= r.status_code < 500 and r.status_code != 429:
                raise LLMUnavailable(f"LLM request rejected ({r.status_code})")
            r.raise_for_status()
            return r.json()
        except LLMUnavailable:
            raise
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(2)
    raise LLMUnavailable(str(last))


def text_of(resp: dict) -> str:
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()


def json_completion(system: str, user_content, max_tokens: int = 600) -> dict:
    """Ask for a single JSON object; one retry on invalid JSON, then LLMUnavailable."""
    for _ in range(2):
        resp = messages(system, [{"role": "user", "content": user_content}], max_tokens=max_tokens)
        txt = text_of(resp)
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMUnavailable("invalid JSON from LLM")
