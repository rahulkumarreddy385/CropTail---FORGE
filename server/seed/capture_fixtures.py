"""Replace the synthetic weather fixtures with REAL Open-Meteo data for the seeded plot (needs internet).

Run before the demo:  python -m seed.capture_fixtures
It also prints the heaviest-rain days in the last 120 days so you can pick a real DEMO_EVENT_DATE.
NDVI stays synthetic unless Earth Engine credentials are configured (then the live path is used anyway).
"""
import json
from datetime import timedelta

from config.settings import settings
from seed.make_fixtures import FIXTURES
from services.http import get_json
from services.weather import ARCHIVE_URL, FORECAST_URL, OBS_DAILY

LAT, LON = 26.9310, 81.1920  # P2 "Nahar wala khet"


def main() -> None:
    today = settings.today()
    tz = settings.timezone.key
    meta = {"kind": "captured", "note": f"Real Open-Meteo data captured on {today} for {LAT},{LON}."}

    start = today - timedelta(days=500)
    obs = get_json(ARCHIVE_URL, {"latitude": LAT, "longitude": LON, "daily": OBS_DAILY, "timezone": tz,
                                 "start_date": start.isoformat(), "end_date": (today - timedelta(days=6)).isoformat()},
                   timeout=60)
    recent = get_json(FORECAST_URL, {"latitude": LAT, "longitude": LON, "daily": OBS_DAILY, "timezone": tz,
                                     "start_date": (today - timedelta(days=5)).isoformat(),
                                     "end_date": (today - timedelta(days=1)).isoformat()})
    daily = {k: obs["daily"][k] + recent["daily"][k] for k in ("time", "precipitation_sum", "temperature_2m_max",
                                                                "weather_code")}
    (FIXTURES / "observed.json").write_text(json.dumps({"_meta": meta, "daily": daily}, indent=1))

    normals = get_json(ARCHIVE_URL, {"latitude": LAT, "longitude": LON, "daily": "precipitation_sum", "timezone": tz,
                                     "start_date": "1991-01-01", "end_date": "2020-12-31"}, timeout=90)
    sums: dict[str, list[float]] = {}
    for t, v in zip(normals["daily"]["time"], normals["daily"]["precipitation_sum"]):
        if v is not None:
            sums.setdefault(str(int(t[5:7])), []).append(v)
    means = {m: round(sum(v) / len(v), 2) for m, v in sums.items()}
    (FIXTURES / "normals.json").write_text(json.dumps({"_meta": meta, "mean_daily_precip_mm": means}, indent=1))

    fc = get_json(FORECAST_URL, {"latitude": LAT, "longitude": LON, "forecast_days": 7, "timezone": tz,
                                 "hourly": "precipitation,precipitation_probability,temperature_2m,wind_speed_10m",
                                 "daily": "precipitation_sum,temperature_2m_max,wind_gusts_10m_max,weather_code"})
    h, d = fc["hourly"], fc["daily"]
    template = {"_meta": {**meta, "note": meta["note"] + " Forecast is replayed from 'today' when cached."},
                "hourly": {"offset_hour": list(range(len(h["time"]))),
                           **{k: h[k] for k in h if k != "time"}},
                "daily": {"offset_day": list(range(len(d["time"]))), **{k: d[k] for k in d if k != "time"}}}
    (FIXTURES / "forecast.json").write_text(json.dumps(template, indent=1))

    pairs = [(t, v) for t, v in zip(daily["time"], daily["precipitation_sum"]) if v is not None
             and t >= (today - timedelta(days=120)).isoformat()]
    print("Captured real fixtures. Heaviest rain days (last 120 days) for DEMO_EVENT_DATE:")
    for t, v in sorted(pairs, key=lambda x: -x[1])[:5]:
        print(f"  {t}: {v} mm")


if __name__ == "__main__":
    main()
