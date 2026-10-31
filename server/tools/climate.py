"""L3 spray check, L5 risk score, L8 NDVI selection. Pure functions over weather/satellite data."""
from datetime import date, datetime, timedelta

from config import rules
from tools.money import change_pct


def _fmt_day(d: str) -> str:
    return datetime.fromisoformat(d[:10]).strftime("%d %b")


# ---------- L3 spray check ----------
def spray_check(hourly: list[dict], day: date, lookahead_hours: int) -> dict:
    start = datetime.combine(day, datetime.min.time()).replace(hour=rules.SPRAY_WINDOW_START_HOUR)
    end = datetime.combine(day, datetime.min.time()).replace(hour=rules.SPRAY_WINDOW_END_HOUR)
    look_end = end + timedelta(hours=lookahead_hours)
    parsed = [(datetime.fromisoformat(h["time"]), h) for h in hourly]
    window = [h for t, h in parsed if start <= t < end]
    span = [h for t, h in parsed if start <= t < look_end]
    if len(window) < (rules.SPRAY_WINDOW_END_HOUR - rules.SPRAY_WINDOW_START_HOUR):
        return {"verdict": None, "reasons": ["Forecast not available for that date."], "reason_codes": ["no_forecast"],
                "best_window": None, "forecast_hours_used": len(span)}

    reasons, codes = [], []
    total_rain = round(sum(h["precipitation"] or 0 for h in span), 1)
    wet_hours = [h for h in span if (h["precipitation"] or 0) > 0]
    max_prob = max((h["precipitation_probability"] or 0) for h in span)
    rain = total_rain >= rules.SPRAY_RAIN_TOTAL_MM or max_prob >= rules.SPRAY_RAIN_PROB_PCT
    if rain:
        codes.append("rain")
        if wet_hours:
            peak = max(wet_hours, key=lambda h: h["precipitation"])
            reasons.append(f"Rain expected: {total_rain} mm in the next {12 + lookahead_hours} hours, heaviest "
                           f"around {peak['time'][11:16]} on {_fmt_day(peak['time'])}. Spray may wash off.")
        else:
            reasons.append(f"Rain chance up to {max_prob}% during or after the spray window.")
    if all((h["wind_speed_10m"] or 0) > rules.SPRAY_MAX_WIND_KMH for h in window):
        codes.append("wind")
        reasons.append(f"Wind above {rules.SPRAY_MAX_WIND_KMH} km/h all day: spray will drift.")
    hot = all((h["temperature_2m"] or 0) > rules.SPRAY_HEAT_C for h in window)

    def blocks(candidates):
        out = []
        for i in range(len(window) - rules.SPRAY_BLOCK_HOURS + 1):
            blk = window[i:i + rules.SPRAY_BLOCK_HOURS]
            if any((h["precipitation"] or 0) > 0 or (h["precipitation_probability"] or 0) >= rules.SPRAY_RAIN_PROB_PCT
                   for h in blk):
                continue
            out.append(blk)
        return out

    def as_window(blk):
        last = datetime.fromisoformat(blk[-1]["time"]) + timedelta(hours=1)
        return {"start": blk[0]["time"], "end": last.strftime("%Y-%m-%dT%H:%M")}

    if codes:
        verdict, best = "not_advised", None
    elif hot:
        verdict = "caution"
        codes.append("heat")
        cand = blocks(window)
        coolest = min(cand, key=lambda b: sum(h["temperature_2m"] for h in b)) if cand else None
        best = as_window(coolest) if coolest else None
        reasons.append(f"Very hot (above {rules.SPRAY_HEAT_C} °C) all day. Spray in the coolest hours.")
    else:
        cand = blocks(window)
        if cand:
            calm = min(cand, key=lambda b: (sum(h["wind_speed_10m"] for h in b), b[0]["time"]))
            verdict, best = "ok", as_window(calm)
            reasons.append(f"No rain expected and wind is light. Best time {best['start'][11:16]}-{best['end'][11:16]}.")
        else:
            verdict, best = "not_advised", None
            codes.append("rain")
            reasons.append("No 3-hour dry window found in the day.")
    return {"verdict": verdict, "reasons": reasons, "reason_codes": codes, "best_window": best,
            "forecast_hours_used": len(span), "date": day.isoformat()}


# ---------- L5 risk score ----------
def risk_score(daily: list[dict], stage: str, today: date) -> dict:
    days = [x for x in daily if x["date"] >= today.isoformat()][: rules.RISK_FORECAST_DAYS]
    raw, drivers = 0, []
    for x in days:
        pts, why = 0, []
        rain = x["precipitation_sum"] or 0
        if rain >= rules.RISK_HEAVY_RAIN_MM:
            pts += rules.RISK_POINTS["heavy_rain"]
            why.append(f"Heavy rain {rain:g} mm forecast on {x['date']}")
        elif rain >= rules.RISK_MODERATE_RAIN_MM:
            pts += rules.RISK_POINTS["moderate_rain"]
            why.append(f"Moderate rain {rain:g} mm forecast on {x['date']}")
        if (x.get("temperature_2m_max") or 0) >= rules.RISK_HEAT_C:
            pts += rules.RISK_POINTS["heat"]
            why.append(f"Heat {x['temperature_2m_max']:g} °C forecast on {x['date']}")
        if (x.get("wind_gusts_10m_max") or 0) >= rules.RISK_GUST_KMH:
            pts += rules.RISK_POINTS["gust"]
            why.append(f"Wind gusts {x['wind_gusts_10m_max']:g} km/h on {x['date']}")
        if x.get("weather_code") in rules.HAIL_WEATHER_CODES:
            pts += rules.RISK_POINTS["hail"]
            why.append(f"Thunderstorm with hail possible on {x['date']}")
        if pts > raw:
            raw, drivers = pts, why
        elif pts == raw and pts > 0 and not drivers:
            drivers = why
    sensitive = stage in rules.SENSITIVE_STAGES
    score = int(raw * rules.RISK_SENSITIVE_MULTIPLIER) if sensitive else raw
    level = "low"
    for lo, hi, name in rules.RISK_LEVELS:
        if score >= lo and (hi is None or score <= hi):
            level = name
    if sensitive and raw > 0:
        drivers = drivers + [f"Crop is at a sensitive stage ({stage.replace('_', ' ')})"]
    return {"level": level, "score": score, "raw_score": raw, "stage": stage, "drivers": drivers,
            "days_considered": len(days)}


# ---------- L8 NDVI before/after ----------
def ndvi_change(images: list[dict], event_date: date, harvest_dates: list[str]) -> dict:
    def clearest(lo: date, hi: date):
        valid = [i for i in images if lo.isoformat() <= i["date"] <= hi.isoformat()
                 and i.get("ndvi") is not None and i["masked_pct"] <= rules.NDVI_MAX_MASKED_PCT]
        return min(valid, key=lambda i: (i["masked_pct"], i["date"])) if valid else None

    w = rules.NDVI_WINDOW_DAYS
    before = clearest(event_date - timedelta(days=w), event_date - timedelta(days=1))
    after = clearest(event_date + timedelta(days=1), event_date + timedelta(days=w))
    notes = []
    if before is None:
        notes.append("No cloud-free satellite image in the window before the event.")
    if after is None:
        notes.append("No cloud-free satellite image in the window after the event.")
    if before and after and any(before["date"] < h <= after["date"] for h in harvest_dates):
        notes.append("Harvest occurred between images; NDVI drop may reflect harvesting, not damage.")
    return {
        "ndvi_before": before["ndvi"] if before else None, "before_date": before["date"] if before else None,
        "ndvi_after": after["ndvi"] if after else None, "after_date": after["date"] if after else None,
        "ndvi_change_pct": change_pct(after["ndvi"], before["ndvi"]) if before and after else None,
        "notes": notes,
    }


def valid_series(images: list[dict]) -> list[dict]:
    return [i for i in images if i.get("ndvi") is not None and i["masked_pct"] <= rules.NDVI_MAX_MASKED_PCT]
