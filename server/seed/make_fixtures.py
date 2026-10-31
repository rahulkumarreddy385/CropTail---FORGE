"""Writes the SYNTHETIC offline fixtures used when USE_CACHED_DATA=true or an API is unreachable.

These are made-up but plausible values so the demo and tests run without a network. They are
labelled "synthetic" everywhere they surface (API `fixture_kind`, UI chip, evidence pack).
Before a real demo, run `python -m seed.capture_fixtures` with internet access to replace the
weather/NDVI fixtures with real captured data for the seeded plot locations.

Run: python -m seed.make_fixtures
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
META = {"kind": "synthetic", "note": "Synthetic sample data for offline demo/testing. Not observed weather."}


def forecast_template() -> dict:
    """7 days of hourly + daily values, keyed by day offset from 'today' (shifted at load time)."""
    hourly = {"offset_hour": [], "precipitation": [], "precipitation_probability": [],
              "temperature_2m": [], "wind_speed_10m": []}
    daily = {"offset_day": [], "precipitation_sum": [], "temperature_2m_max": [],
             "wind_gusts_10m_max": [], "weather_code": []}
    for d in range(7):
        day_rain = 0.0
        for h in range(24):
            temp = 18 + 12 * max(0.0, 1 - abs(h - 14) / 8)  # ~18 C night, ~30 C at 14:00
            wind = 5 + 4 * max(0.0, 1 - abs(h - 15) / 6)
            rain, prob = 0.0, 5
            if d == 1 and h == 14:
                rain, prob = 3.2, 70
            elif d == 1 and h in (13, 15):
                prob = 55
            if d == 3 and 8 <= h <= 21:
                rain = [3.0, 5.0, 7.0, 9.0, 10.0, 9.0, 8.0, 7.0, 6.0, 6.0, 5.0, 4.0, 2.0, 1.0][h - 8]
                prob, wind, temp = 90, wind + 18, temp - 5
            hourly["offset_hour"].append(d * 24 + h)
            hourly["precipitation"].append(rain)
            hourly["precipitation_probability"].append(prob)
            hourly["temperature_2m"].append(round(temp, 1))
            hourly["wind_speed_10m"].append(round(wind, 1))
            day_rain += rain
        daily["offset_day"].append(d)
        daily["precipitation_sum"].append(round(day_rain, 1))
        daily["temperature_2m_max"].append(26.0 if d == 3 else 30.0)
        daily["wind_gusts_10m_max"].append(46.0 if d == 3 else 18.0)
        daily["weather_code"].append(65 if d == 3 else (61 if d == 1 else 1))
    return {"_meta": META, "hourly": hourly, "daily": daily}


def observed_series() -> dict:
    rnd = random.Random(42)
    start, end = date(2025, 6, 1), date(2026, 10, 29)
    out = {"time": [], "precipitation_sum": [], "temperature_2m_max": [], "weather_code": []}
    d = start
    while d <= end:
        m = d.month
        wet = {6: 0.35, 7: 0.6, 8: 0.55, 9: 0.4, 10: 0.12}.get(m, 0.05)
        rain = round(rnd.expovariate(1 / 12), 1) if rnd.random() < wet else 0.0
        rain = min(rain, 55.0)
        tmax = {6: 38, 7: 33, 8: 32, 9: 32, 10: 31, 11: 28}.get(m, 25) + rnd.uniform(-2, 2)
        if d == date(2026, 10, 14):
            rain = 78.4
        if d == date(2026, 10, 15):
            rain = 21.0
        if date(2026, 10, 16) <= d <= date(2026, 10, 29):
            rain = 0.0
        out["time"].append(d.isoformat())
        out["precipitation_sum"].append(rain)
        out["temperature_2m_max"].append(round(tmax, 1))
        out["weather_code"].append(63 if rain >= 10 else (61 if rain > 0 else 1))
        d += timedelta(days=1)
    return {"_meta": META, "daily": out}


def normals() -> dict:
    # mean daily rainfall (mm/day) by month, roughly typical for central Uttar Pradesh
    return {"_meta": META, "mean_daily_precip_mm": {
        "1": 0.6, "2": 0.6, "3": 0.4, "4": 0.2, "5": 0.6, "6": 3.6, "7": 9.2, "8": 8.6,
        "9": 5.9, "10": 1.2, "11": 0.2, "12": 0.2}}


def ndvi_series() -> dict:
    p2 = [  # Kharif 2025 + Kharif 2026 paddy on P2
        ("2025-07-12", 0.24, 10), ("2025-08-21", 0.58, 22), ("2025-09-15", 0.77, 14),
        ("2025-10-10", 0.69, 8), ("2025-11-04", 0.27, 5),
        ("2026-07-05", 0.21, 18), ("2026-07-15", 0.29, 64), ("2026-07-25", 0.36, 26),
        ("2026-08-04", 0.44, 81), ("2026-08-14", 0.55, 21), ("2026-08-24", 0.63, 47),
        ("2026-09-03", 0.70, 16), ("2026-09-13", 0.76, 12), ("2026-09-23", 0.78, 9),
        ("2026-10-03", 0.75, 38), ("2026-10-08", 0.73, 11), ("2026-10-13", 0.72, 72),
        ("2026-10-18", 0.49, 4), ("2026-10-23", 0.44, 9), ("2026-10-28", 0.26, 6),
    ]
    p1 = [
        ("2026-08-24", 0.22, 20), ("2026-09-03", 0.31, 15), ("2026-09-13", 0.42, 11),
        ("2026-09-23", 0.51, 8), ("2026-10-03", 0.57, 35), ("2026-10-08", 0.58, 12),
        ("2026-10-18", 0.55, 14), ("2026-10-28", 0.56, 7),
    ]
    fmt = lambda s: [{"date": d, "ndvi": v, "masked_pct": m} for d, v, m in s]
    return {"_meta": META, "plots": {"P1": fmt(p1), "P2": fmt(p2)}}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "forecast.json").write_text(json.dumps(forecast_template(), indent=1))
    (FIXTURES / "observed.json").write_text(json.dumps(observed_series(), indent=1))
    (FIXTURES / "normals.json").write_text(json.dumps(normals(), indent=1))
    (FIXTURES / "ndvi.json").write_text(json.dumps(ndvi_series(), indent=1))
    with open(FIXTURES / "mandi.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["crop", "market", "arrival_date", "modal_price", "source"])
        w.writerow(["paddy", "Barabanki", "2026-10-28", "2300", "sample placeholder"])
        w.writerow(["wheat", "Barabanki", "2026-10-28", "2450", "sample placeholder"])
        w.writerow(["tomato", "Barabanki", "2026-10-28", "1600", "sample placeholder"])
    with open(FIXTURES / "benchmarks.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["crop", "state", "year", "cost_per_quintal_inr", "source"])
        w.writerow(["paddy", "Uttar Pradesh", "2023-24", "1450", "sample placeholder"])
        w.writerow(["wheat", "Uttar Pradesh", "2023-24", "1300", "sample placeholder"])
    print("fixtures written to", FIXTURES)


if __name__ == "__main__":
    main()
