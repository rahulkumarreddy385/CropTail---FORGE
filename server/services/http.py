"""Shared HTTP + cache helpers for external services. One retry with 2 s backoff (spec E-retry policy)."""
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

from config.settings import settings

FIXTURES = Path(__file__).resolve().parent.parent / "seed" / "fixtures"

# last mode seen per integration, reported by /api/health
LAST_MODE: dict[str, str] = {}


class DataUnavailable(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def get_json(url: str, params: dict | None = None, timeout: float = 15.0, headers: dict | None = None):
    last_exc = None
    for attempt in range(2):
        try:
            r = httpx.get(url, params=params, timeout=timeout, headers=headers)
            if 400 <= r.status_code < 500:
                r.raise_for_status()  # never retry a 4xx
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise
            last_exc = exc
        except Exception as exc:  # network, timeout, bad JSON
            last_exc = exc
        if attempt == 0:
            time.sleep(2)
    raise last_exc  # type: ignore[misc]


def _cache_path(namespace: str, key: str) -> Path:
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return settings.cache_dir / f"{namespace}-{h}.json"


def cache_put(namespace: str, key: str, payload) -> None:
    _cache_path(namespace, key).write_text(json.dumps({"saved_at": settings.now().isoformat(), "payload": payload}))


def cache_get(namespace: str, key: str, max_age_hours: float | None = None):
    p = _cache_path(namespace, key)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    saved = datetime.fromisoformat(data["saved_at"])
    if max_age_hours is not None and (settings.now() - saved).total_seconds() > max_age_hours * 3600:
        return None
    return data


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())
