"""The only place that talks to Gemini's generateContent API over HTTP.

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
    if not enabled():
        raise LLMUnavailable("no key")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(msgs),
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [{
            "name": tool["name"],
            "description": tool["description"],
            "parameters": _gemini_schema(tool["input_schema"]),
        } for tool in tools]}]
    headers = {"x-goog-api-key": settings.llm_api_key, "content-type": "application/json"}
    last = None
    for attempt in range(2):
        try:
            r = httpx.post(f"{settings.llm_base_url}/models/{settings.llm_model}:generateContent",
                           json=body, headers=headers, timeout=TIMEOUT_S)
            if 400 <= r.status_code < 500 and r.status_code != 429:
                raise LLMUnavailable(f"LLM request rejected ({r.status_code})")
            r.raise_for_status()
            payload = r.json()
            candidates = payload.get("candidates") or []
            if not candidates or not candidates[0].get("content"):
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
            return {"content": content}
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
