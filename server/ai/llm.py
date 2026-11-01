"""The only place that talks to Gemini's generateContent API over HTTP.

Every function raises LLMUnavailable when no key is configured or the call fails after bounded retries;
callers then switch to the deterministic fallback (spec E4/E5).
"""
import json
import random
import re
import time

import httpx

from config.settings import settings

TIMEOUT_S = 20
MAX_ATTEMPTS = 3
_LAST_STATUS = "configured"


class LLMUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(settings.llm_api_key)


def provider_status() -> str:
    return _LAST_STATUS if enabled() else "fallback"


def _failure_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status = exc.response.status_code
        if status in (401, 403):
            return f"Gemini rejected the API key or access (HTTP {status}). Check GEMINI_API_KEY and model access."
        if status == 404:
            return "Gemini could not find the configured model. Check LLM_MODEL."
        if status == 429:
            return "Gemini rate or quota limit reached. Check the API quota and try again later."
        if status in (500, 502, 503, 504):
            return (f"Gemini is temporarily unavailable (HTTP {status}); this is a Google service issue, "
                    "not an invalid-key error. Please try again shortly.")
        return f"Gemini rejected the request (HTTP {status}). Check the model and request configuration."
    return "Could not reach Gemini or read its response. Check the network and Gemini API availability."


def _gemini_schema(schema: dict) -> dict:
    """Translate the tool JSON schema to Gemini's supported schema representation."""
    out = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "type" and isinstance(value, str):
            out[key] = value.upper()
        elif key == "properties":
            out[key] = {name: _gemini_schema(prop) for name, prop in value.items()}
        elif key == "items" and isinstance(value, dict):
            out[key] = _gemini_schema(value)
        else:
            out[key] = value
    return out


def _gemini_contents(msgs: list[dict]) -> list[dict]:
    contents = []
    tool_names = {}
    for msg in msgs:
        role = "model" if msg["role"] == "assistant" else "user"
        blocks = msg.get("content", "")
        if isinstance(blocks, str):
            parts = [{"text": blocks}]
        else:
            parts = []
            for block in blocks:
                kind = block.get("type")
                if kind == "text":
                    parts.append({"text": block.get("text", "")})
                elif kind == "image":
                    source = block["source"]
                    parts.append({"inlineData": {"mimeType": source["media_type"], "data": source["data"]}})
                elif kind == "tool_use":
                    tool_names[block["id"]] = block["name"]
                    parts.append({"functionCall": {
                        "name": block["name"], "args": block.get("input") or {}, "id": block["id"],
                    }})
                elif kind == "tool_result":
                    name = tool_names.get(block["tool_use_id"])
                    if not name:
                        raise LLMUnavailable("Gemini tool result has no matching function call")
                    response_key = "error" if block.get("is_error") else "result"
                    parts.append({"functionResponse": {
                        "name": name, "id": block["tool_use_id"],
                        "response": {response_key: block.get("content", "")},
                    }})
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


def messages(system: str, msgs: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024) -> dict:
    global _LAST_STATUS
    if not enabled():
        raise LLMUnavailable("no key")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(msgs),
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [{
            "name": tool["name"],
            "description": tool["description"],
            "parameters": _gemini_schema(tool["input_schema"]),
        } for tool in tools]}]
    headers = {"x-goog-api-key": settings.llm_api_key, "content-type": "application/json"}
    last = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = httpx.post(f"{settings.llm_base_url}/models/{settings.llm_model}:generateContent",
                           json=body, headers=headers, timeout=TIMEOUT_S)
            if 400 <= r.status_code < 500 and r.status_code != 429:
                _LAST_STATUS = "unavailable"
                raise LLMUnavailable(_failure_message(httpx.HTTPStatusError(
                    "Gemini rejected request", request=r.request, response=r,
                )))
            r.raise_for_status()
            payload = r.json()
            candidates = payload.get("candidates") or []
            if not candidates or not candidates[0].get("content"):
                _LAST_STATUS = "unavailable"
                raise LLMUnavailable("Gemini returned no candidate")
            content = []
            for part in candidates[0]["content"].get("parts", []):
                if part.get("text"):
                    content.append({"type": "text", "text": part["text"]})
                call = part.get("functionCall")
                if call:
                    content.append({
                        "type": "tool_use",
                        "id": call.get("id") or f"gemini-{len(content)}",
                        "name": call["name"],
                        "input": call.get("args") or {},
                    })
            if not any(block["type"] == "tool_use" or block["text"].strip()
                       for block in content):
                _LAST_STATUS = "unavailable"
                raise LLMUnavailable("Gemini returned no text or function call.")
            _LAST_STATUS = "live"
            return {"content": content}
        except LLMUnavailable:
            raise
        except Exception as exc:
            last = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep((2 ** attempt) + random.uniform(0, 0.25))
    _LAST_STATUS = "unavailable"
    raise LLMUnavailable(_failure_message(last))


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
