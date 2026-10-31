import os
import sys
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("USE_CACHED_DATA", "true")
    monkeypatch.setenv("ALLOW_SAMPLE_FIXTURES", "true")
    monkeypatch.setenv("CROPTRAIL_NOW", "2026-10-30T10:00:00+05:30")
    monkeypatch.setenv("DISABLE_SCHEDULER", "true")
    monkeypatch.setenv("ALLOW_SIMULATION", "true")
    monkeypatch.setenv("DEMO_EVENT_DATE", "2026-10-14")
    for k in ("LLM_API_KEY", "GEE_SERVICE_ACCOUNT_JSON", "DATA_GOV_IN_API_KEY", "MANDI_RESOURCE_ID"):
        monkeypatch.setenv(k, "")
    from seed import seed
    seed.reset_db()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn():
    from models import db
    c = db.connect()
    yield c
    c.commit()
    c.close()


def hourly_fixture(day, rain_at=None, rain_mm=0.0, wind=8.0, temp=28.0, prob=5):
    """48 h of hourly forecast starting at 00:00 of `day`."""
    from datetime import datetime, timedelta
    start = datetime.combine(day, datetime.min.time())
    out = []
    for h in range(48):
        t = start + timedelta(hours=h)
        rain = rain_mm if rain_at is not None and h == rain_at else 0.0
        out.append({"time": t.strftime("%Y-%m-%dT%H:%M"), "precipitation": rain,
                    "precipitation_probability": 60 if rain else prob, "temperature_2m": temp,
                    "wind_speed_10m": wind})
    return out
