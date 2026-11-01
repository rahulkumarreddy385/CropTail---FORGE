"""Agmarknet mandi prices via data.gov.in, saved-real-data cache, and optional sample fixtures."""
import csv
from datetime import datetime

from config.rules import MANDI_COMMODITY
from config.settings import settings
from services.http import FIXTURES, LAST_MODE, cache_get, cache_put, get_json

API = "https://api.data.gov.in/resource/{rid}"


def _fixture_price(crop: str, market: str) -> dict | None:
    with open(FIXTURES / "mandi.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["crop"] == crop]
    match = [r for r in rows if r["market"].lower() == (market or "").lower()] or rows
    if not match:
        return None
    r = sorted(match, key=lambda x: x["arrival_date"])[-1]
    return {"crop": crop, "market": r["market"], "modal_price": float(r["modal_price"]),
            "arrival_date": r["arrival_date"], "mode": "cached", "source": r["source"]}


def get_price(crop: str, market: str) -> dict | None:
    """Latest modal price (₹/quintal) for crop at market, or None when nothing is known."""
    key = f"{crop}:{market}"
    live_ok = settings.data_gov_in_api_key and settings.mandi_resource_id and not settings.use_cached_data
    commodity = MANDI_COMMODITY.get(crop)
    if live_ok and commodity:
        try:
            params = {"api-key": settings.data_gov_in_api_key, "format": "json", "limit": 100,
                      "filters[commodity]": commodity}
            if market:
                params["filters[market]"] = market
            raw = get_json(API.format(rid=settings.mandi_resource_id),
                           params)
            recs = raw.get("records", [])
            if recs:
                def d(r):
                    return datetime.strptime(r["arrival_date"], "%d/%m/%Y").date()
                r = max(recs, key=d)
                out = {"crop": crop, "market": r["market"], "modal_price": float(r["modal_price"]),
                       "arrival_date": d(r).isoformat(), "mode": "live", "source": "Agmarknet via data.gov.in"}
                cache_put("mandi", key, out)
                LAST_MODE["mandi"] = "live"
                return out
        except Exception:
            pass
    cached = cache_get("mandi", key)
    if cached:
        LAST_MODE["mandi"] = "cached"
        return {**cached["payload"], "mode": "cached"}
    if settings.sample_data_enabled:
        LAST_MODE["mandi"] = "cached"
        return _fixture_price(crop, market)
    LAST_MODE["mandi"] = "unavailable"
    return None


def get_benchmark(crop: str, state: str) -> dict | None:
    if not settings.sample_data_enabled:
        return None
    with open(FIXTURES / "benchmarks.csv") as f:
        rows = [r for r in csv.DictReader(f)
                if r["crop"] == crop and r["state"].lower() == (state or "").lower()]
    if not rows:
        return None
    r = sorted(rows, key=lambda x: x["year"])[-1]
    return {"crop": crop, "state": r["state"], "year": r["year"],
            "cost_per_quintal": float(r["cost_per_quintal_inr"]), "source": r["source"]}
