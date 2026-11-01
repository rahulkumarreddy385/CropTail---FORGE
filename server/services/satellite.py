"""Sentinel-2 L2A NDVI via Google Earth Engine, with optional fixture fallback for seeded plots.

Returns per-image {date, ndvi (median over the plot AOI), masked_pct} lists; choosing images and
computing change is deterministic logic in tools/ndvi.py.
"""
import json
import math
from datetime import date, timedelta

from config.settings import settings
from services.http import LAST_MODE, cache_get, cache_put, fixture

# Scene Classification Layer classes treated as invalid: saturated, cloud shadow, cloud medium/high, cirrus, snow
SCL_INVALID = [1, 3, 8, 9, 10, 11]
_ee = None


def _init_ee():
    global _ee
    if _ee is not None:
        return _ee
    path = settings.gee_service_account_json
    if not path:
        return None
    try:
        import ee  # type: ignore
        info = json.loads(open(path).read())
        creds = ee.ServiceAccountCredentials(info["client_email"], path)
        ee.Initialize(creds, project=info.get("project_id"))
        _ee = ee
        return ee
    except Exception:
        return None


def aoi_radius_m(area_acres: float) -> float:
    return math.sqrt(area_acres * 4046.8564224 / math.pi)


def _gee_images(lat: float, lon: float, area_acres: float, start: date, end: date) -> list[dict]:
    ee = _init_ee()
    if ee is None:
        raise RuntimeError("Earth Engine not configured")
    aoi = ee.Geometry.Point([lon, lat]).buffer(aoi_radius_m(area_acres))
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi).filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat()))

    def per_image(img):
        scl = img.select("SCL")
        invalid = scl.remap(SCL_INVALID, [1] * len(SCL_INVALID), 0)
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi").updateMask(invalid.Not())
        masked = invalid.reduceRegion(ee.Reducer.mean(), aoi, 10).get("remapped")
        med = ndvi.reduceRegion(ee.Reducer.median(), aoi, 10).get("ndvi")
        return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "masked": masked, "ndvi": med})

    feats = col.map(per_image).getInfo()["features"]
    by_date: dict[str, dict] = {}
    for f in feats:
        p = f["properties"]
        masked_pct = round(100 * (p.get("masked") or 0), 1)
        item = {"date": p["date"], "ndvi": None if p.get("ndvi") is None else round(p["ndvi"], 3),
                "masked_pct": masked_pct}
        prev = by_date.get(p["date"])  # several tiles per day: keep the clearer one
        if prev is None or masked_pct < prev["masked_pct"]:
            by_date[p["date"]] = item
    return sorted(by_date.values(), key=lambda x: x["date"])


def get_images(plot: dict, start: date, end: date) -> dict | None:
    """None means no satellite data at all for this plot (spec E14)."""
    key = f"{plot['lat']:.4f},{plot['lon']:.4f},{plot['area_acres']}:{start}:{end}"
    if not settings.use_cached_data and settings.gee_service_account_json:
        try:
            imgs = _gee_images(plot["lat"], plot["lon"], plot["area_acres"], start, end)
            cache_put("ndvi", key, imgs)
            LAST_MODE["satellite"] = "live"
            return {"images": imgs, "mode": "live", "fixture_kind": None, "source": "Sentinel-2 L2A via Earth Engine"}
        except Exception:
            cached = cache_get("ndvi", key)
            if cached:
                LAST_MODE["satellite"] = "cached"
                return {"images": cached["payload"], "mode": "cached", "fixture_kind": "captured",
                        "source": "Sentinel-2 L2A (cached)"}
    else:
        cached = cache_get("ndvi", key)
        if cached:
            LAST_MODE["satellite"] = "cached"
            return {"images": cached["payload"], "mode": "cached", "fixture_kind": "captured",
                    "source": "Sentinel-2 L2A (cached)"}
    if not settings.sample_data_enabled:
        LAST_MODE["satellite"] = "unavailable"
        return None
    fx = fixture("ndvi.json")
    series = fx["plots"].get(plot["plot_id"])
    if series is None:
        return None
    LAST_MODE["satellite"] = "cached"
    imgs = [x for x in series if start.isoformat() <= x["date"] <= end.isoformat()]
    return {"images": imgs, "mode": "cached", "fixture_kind": fx["_meta"]["kind"],
            "source": "Sentinel-2 NDVI (sample fixture)"}
