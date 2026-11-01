"""Open-Meteo client (forecast, observed history, 1991-2020 normals) with cache and optional fixtures."""
from datetime import date, datetime, timedelta

from config.settings import settings
from services.http import LAST_MODE, DataUnavailable, cache_get, cache_put, fixture, get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = "precipitation,precipitation_probability,temperature_2m,wind_speed_10m"
DAILY = "precipitation_sum,temperature_2m_max,wind_gusts_10m_max,weather_code"
OBS_DAILY = "precipitation_sum,temperature_2m_max,weather_code"


def _key(lat: float, lon: float) -> str:
    return f"{lat:.3f},{lon:.3f}"


def _normalise_forecast(raw: dict) -> dict:
    h, d = raw["hourly"], raw["daily"]
    hourly = [{"time": t, "precipitation": h["precipitation"][i] or 0.0,
               "precipitation_probability": h["precipitation_probability"][i] or 0,
               "temperature_2m": h["temperature_2m"][i], "wind_speed_10m": h["wind_speed_10m"][i]}
              for i, t in enumerate(h["time"])]
    daily = [{"date": t, "precipitation_sum": d["precipitation_sum"][i] or 0.0,
              "temperature_2m_max": d["temperature_2m_max"][i],
              "wind_gusts_10m_max": d["wind_gusts_10m_max"][i], "weather_code": d["weather_code"][i]}
             for i, t in enumerate(d["time"])]
    return {"hourly": hourly, "daily": daily}


def _forecast_fixture() -> dict:
    fx = fixture("forecast.json")
    start = datetime.combine(settings.today(), datetime.min.time())
    h, d = fx["hourly"], fx["daily"]
    raw = {
        "hourly": {**{k: h[k] for k in h if k != "offset_hour"},
                   "time": [(start + timedelta(hours=o)).strftime("%Y-%m-%dT%H:%M") for o in h["offset_hour"]]},
        "daily": {**{k: d[k] for k in d if k != "offset_day"},
                  "time": [(start + timedelta(days=o)).date().isoformat() for o in d["offset_day"]]},
    }
    out = _normalise_forecast(raw)
    out.update(mode="cached", fixture_kind=fx["_meta"]["kind"], fetched_at=settings.now().isoformat(), notice=None)
    return out


def _cached_forecast(key: str) -> dict | None:
    cached = cache_get("forecast", key, max_age_hours=24)
    if not cached:
        return None
    out = dict(cached["payload"])
    saved = datetime.fromisoformat(cached["saved_at"]).strftime("%d %b %H:%M")
    out.update(mode="cached", fixture_kind="captured", fetched_at=cached["saved_at"],
               notice=f"Weather data unavailable right now. Showing last saved forecast from {saved}.")
    LAST_MODE["weather"] = "cached"
    return out


def get_forecast(lat: float, lon: float) -> dict:
    """7-day hourly + daily forecast for a point. Raises DataUnavailable (-> 503) per spec E12."""
    key = _key(lat, lon)
    if settings.use_cached_data:
        if settings.allow_sample_fixtures:
            LAST_MODE["weather"] = "cached"
            return _forecast_fixture()
        cached = _cached_forecast(key)
        if cached:
            return cached
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("No saved real weather forecast is available. Connect to the internet and try again.")
    try:
        raw = get_json(FORECAST_URL, {"latitude": lat, "longitude": lon, "hourly": HOURLY, "daily": DAILY,
                                      "forecast_days": 7, "timezone": settings.timezone.key})
        out = _normalise_forecast(raw)
        cache_put("forecast", key, out)
        LAST_MODE["weather"] = "live"
        out.update(mode="live", fixture_kind=None, fetched_at=settings.now().isoformat(), notice=None)
        return out
    except Exception:
        cached = _cached_forecast(key)
        if cached:
            return cached
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("Weather data unavailable. Try again in a few minutes.")


def get_observed(lat: float, lon: float, start: date, end: date) -> dict:
    """Observed daily weather (gridded model analysis) for [start, end]. Missing days come back as None."""
    key = f"{_key(lat, lon)}:{start}:{end}"
    if settings.use_cached_data:
        if settings.allow_sample_fixtures:
            LAST_MODE["weather"] = "cached"
            fx = fixture("observed.json")
            d = fx["daily"]
            days = [{"date": t, "precipitation_sum": d["precipitation_sum"][i],
                     "temperature_2m_max": d["temperature_2m_max"][i], "weather_code": d["weather_code"][i]}
                    for i, t in enumerate(d["time"]) if start.isoformat() <= t <= end.isoformat()]
            return {"days": _fill(days, start, end), "mode": "cached", "fixture_kind": fx["_meta"]["kind"],
                    "fetched_at": settings.now().isoformat(), "source": "Open-Meteo (sample fixture)"}
        cached = cache_get("observed", key)
        if cached:
            LAST_MODE["weather"] = "cached"
            return {"days": _fill(cached["payload"], start, end), "mode": "cached", "fixture_kind": "captured",
                    "fetched_at": cached["saved_at"], "source": "Open-Meteo (cached)"}
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("No saved real weather observations are available. Connect to the internet and try again.")
    recent = (settings.today() - start).days <= 90
    url = FORECAST_URL if recent else ARCHIVE_URL
    try:
        raw = get_json(url, {"latitude": lat, "longitude": lon, "daily": OBS_DAILY, "start_date": start.isoformat(),
                             "end_date": end.isoformat(), "timezone": settings.timezone.key})
        d = raw["daily"]
        days = [{"date": t, "precipitation_sum": d["precipitation_sum"][i],
                 "temperature_2m_max": d["temperature_2m_max"][i], "weather_code": d["weather_code"][i]}
                for i, t in enumerate(d["time"])]
        cache_put("observed", key, days)
        LAST_MODE["weather"] = "live"
        return {"days": _fill(days, start, end), "mode": "live", "fixture_kind": None,
                "fetched_at": settings.now().isoformat(), "source": "Open-Meteo"}
    except Exception:
        cached = cache_get("observed", key)
        if cached:
            LAST_MODE["weather"] = "cached"
            return {"days": _fill(cached["payload"], start, end), "mode": "cached", "fixture_kind": "captured",
                    "fetched_at": cached["saved_at"], "source": "Open-Meteo (cached)"}
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("Weather data unavailable. Try again in a few minutes.")


def _fill(days: list[dict], start: date, end: date) -> list[dict]:
    by_date = {x["date"]: x for x in days}
    out, d = [], start
    while d <= end:
        out.append(by_date.get(d.isoformat(), {"date": d.isoformat(), "precipitation_sum": None,
                                                "temperature_2m_max": None, "weather_code": None}))
        d += timedelta(days=1)
    return out


def get_monthly_normal(lat: float, lon: float, month: int) -> dict:
    """Mean daily rainfall for a calendar month over 1991-2020."""
    if settings.use_cached_data and settings.allow_sample_fixtures:
        fx = fixture("normals.json")
        LAST_MODE["weather"] = "cached"
        return {"mean_daily_precip_mm": fx["mean_daily_precip_mm"][str(month)], "mode": "cached",
                "fixture_kind": fx["_meta"]["kind"]}
    key = _key(lat, lon)
    cached = cache_get("normals", key)
    if cached:
        LAST_MODE["weather"] = "cached"
        return {"mean_daily_precip_mm": cached["payload"][str(month)], "mode": "cached", "fixture_kind": "captured"}
    if settings.use_cached_data:
        if settings.sample_data_enabled:
            fx = fixture("normals.json")
            return {"mean_daily_precip_mm": fx["mean_daily_precip_mm"][str(month)], "mode": "cached",
                    "fixture_kind": fx["_meta"]["kind"]}
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("No saved real weather normals are available. Connect to the internet and try again.")
    try:
        raw = get_json(ARCHIVE_URL, {"latitude": lat, "longitude": lon, "start_date": "1991-01-01",
                                     "end_date": "2020-12-31", "daily": "precipitation_sum",
                                     "timezone": settings.timezone.key}, timeout=60)
        sums: dict[str, list[float]] = {}
        for t, v in zip(raw["daily"]["time"], raw["daily"]["precipitation_sum"]):
            if v is not None:
                sums.setdefault(str(int(t[5:7])), []).append(v)
        means = {m: round(sum(v) / len(v), 2) for m, v in sums.items()}
        cache_put("normals", key, means)
        LAST_MODE["weather"] = "live"
        return {"mean_daily_precip_mm": means[str(month)], "mode": "live", "fixture_kind": None}
    except Exception:
        if settings.sample_data_enabled:
            fx = fixture("normals.json")
            return {"mean_daily_precip_mm": fx["mean_daily_precip_mm"][str(month)], "mode": "cached",
                    "fixture_kind": fx["_meta"]["kind"]}
        LAST_MODE["weather"] = "unavailable"
        raise DataUnavailable("Weather normals are unavailable. Try again in a few minutes.")
