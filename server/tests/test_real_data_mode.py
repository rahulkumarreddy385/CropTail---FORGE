from datetime import date

import pytest

from services import mandi, satellite, weather
from services.http import DataUnavailable


def _disable_fixtures(monkeypatch):
    monkeypatch.setenv("USE_CACHED_DATA", "true")
    monkeypatch.setenv("ALLOW_SAMPLE_FIXTURES", "false")


def test_weather_does_not_use_fixture_without_opt_in(monkeypatch):
    _disable_fixtures(monkeypatch)
    monkeypatch.setattr(weather, "cache_get", lambda *args, **kwargs: None)

    with pytest.raises(DataUnavailable):
        weather.get_forecast(71.123, 19.456)
    with pytest.raises(DataUnavailable):
        weather.get_observed(71.123, 19.456, date(2020, 1, 1), date(2020, 1, 2))
    with pytest.raises(DataUnavailable):
        weather.get_monthly_normal(71.123, 19.456, 1)


def test_weather_uses_saved_real_forecast_without_fixtures(monkeypatch):
    _disable_fixtures(monkeypatch)
    saved = {
        "saved_at": "2026-10-30T10:00:00+05:30",
        "payload": {"hourly": [], "daily": []},
    }
    monkeypatch.setattr(weather, "cache_get", lambda *args, **kwargs: saved)

    out = weather.get_forecast(71.123, 19.456)

    assert out["mode"] == "cached"
    assert out["fixture_kind"] == "captured"
    assert out["hourly"] == []


def test_mandi_and_benchmark_never_return_fixtures_without_opt_in(monkeypatch):
    _disable_fixtures(monkeypatch)
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "")
    monkeypatch.setenv("MANDI_RESOURCE_ID", "")
    monkeypatch.setattr(mandi, "cache_get", lambda *args, **kwargs: None)

    assert mandi.get_price("paddy", "Lucknow") is None
    assert mandi.get_benchmark("paddy", "Uttar Pradesh") is None


def test_satellite_uses_saved_real_data_or_reports_unavailable(monkeypatch):
    _disable_fixtures(monkeypatch)
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_JSON", "")
    plot = {"plot_id": "P_REAL_ONLY_TEST", "lat": 71.123, "lon": 19.456, "area_acres": 1.0}
    monkeypatch.setattr(satellite, "cache_get", lambda *args, **kwargs: None)

    assert satellite.get_images(plot, date(2026, 1, 1), date(2026, 1, 2)) is None

    saved = {"saved_at": "2026-10-30T10:00:00+05:30", "payload": [{"date": "2026-01-01", "ndvi": 0.5}]}
    monkeypatch.setattr(satellite, "cache_get", lambda *args, **kwargs: saved)
    out = satellite.get_images(plot, date(2026, 1, 1), date(2026, 1, 2))

    assert out["mode"] == "cached"
    assert out["fixture_kind"] == "captured"
    assert out["images"] == saved["payload"]


def test_health_does_not_claim_unverified_integrations_are_live(monkeypatch, client):
    from services.http import LAST_MODE

    monkeypatch.setenv("USE_CACHED_DATA", "false")
    monkeypatch.setenv("ALLOW_SAMPLE_FIXTURES", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "")
    monkeypatch.setenv("MANDI_RESOURCE_ID", "")
    LAST_MODE.clear()

    health = client.get("/api/health").json()

    assert health["weather"] == "configured"
    assert health["satellite"] == "unavailable"
    assert health["mandi"] == "unavailable"
    assert health["sample_data_enabled"] is False


def test_sample_fixtures_require_explicit_offline_demo_mode(monkeypatch):
    monkeypatch.setenv("USE_CACHED_DATA", "false")
    monkeypatch.setenv("ALLOW_SAMPLE_FIXTURES", "true")
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "")
    monkeypatch.setenv("MANDI_RESOURCE_ID", "")
    monkeypatch.setattr(weather, "cache_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(satellite, "cache_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(mandi, "cache_get", lambda *args, **kwargs: None)

    def offline(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(weather, "get_json", offline)

    with pytest.raises(DataUnavailable):
        weather.get_forecast(71.123, 19.456)

    plot = {"plot_id": "P_REAL_ONLY_TEST", "lat": 71.123, "lon": 19.456, "area_acres": 1.0}
    assert satellite.get_images(plot, date(2026, 1, 1), date(2026, 1, 2)) is None
    assert mandi.get_price("paddy", "Lucknow") is None
    assert mandi.get_benchmark("paddy", "Uttar Pradesh") is None


def test_mandi_omits_empty_market_filter(monkeypatch):
    monkeypatch.setenv("USE_CACHED_DATA", "false")
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "test-key")
    monkeypatch.setenv("MANDI_RESOURCE_ID", "test-resource")
    params_seen = {}

    def fake_get_json(url, params):
        params_seen.update(params)
        return {"records": [{"market": "Lucknow", "arrival_date": "30/10/2026", "modal_price": "2400"}]}

    monkeypatch.setattr(mandi, "get_json", fake_get_json)

    out = mandi.get_price("paddy", "")

    assert out["mode"] == "live"
    assert "filters[market]" not in params_seen
