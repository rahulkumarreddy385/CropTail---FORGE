"""Plot-level wrappers combining DB + external data. Used by API routes and agent tools alike."""
from datetime import date, timedelta

from config.settings import settings
from services import mandi, satellite, weather
from tools.climate import ndvi_change, risk_score, spray_check, valid_series
from tools.ledger import active_season, crop_stage, get_plot, season_metrics


def plot_stage(conn, plot_id: str) -> dict | None:
    s = active_season(conn, plot_id)
    if not s:
        return None
    return {**crop_stage(s["crop"], s["sowing_date"], settings.today()), "crop": s["crop"], "season_id": s["season_id"]}


def plot_risk(conn, plot_id: str) -> dict:
    plot = get_plot(conn, plot_id)
    fc = weather.get_forecast(plot["lat"], plot["lon"])
    st = plot_stage(conn, plot_id)
    out = risk_score(fc["daily"], st["stage"] if st else "unknown", settings.today())
    return {**out, "plot_id": plot_id, "forecast_fetched_at": fc["fetched_at"], "mode": fc["mode"],
            "fixture_kind": fc.get("fixture_kind"), "notice": fc.get("notice")}


def plot_spray(conn, plot_id: str, day: date | None = None) -> dict:
    plot = get_plot(conn, plot_id)
    day = day or settings.today() + timedelta(days=1)
    fc = weather.get_forecast(plot["lat"], plot["lon"])
    out = spray_check(fc["hourly"], day, settings.spray_rain_lookahead_hours)
    return {**out, "plot_id": plot_id, "plot_name": plot["name"], "mode": fc["mode"],
            "fixture_kind": fc.get("fixture_kind"), "forecast_fetched_at": fc["fetched_at"], "notice": fc.get("notice")}


def plot_forecast(conn, plot_id: str, days: int = 5) -> dict:
    plot = get_plot(conn, plot_id)
    fc = weather.get_forecast(plot["lat"], plot["lon"])
    today = settings.today().isoformat()
    return {"plot_id": plot_id, "daily": [x for x in fc["daily"] if x["date"] >= today][:days],
            "mode": fc["mode"], "fixture_kind": fc.get("fixture_kind"), "fetched_at": fc["fetched_at"]}


def plot_ndvi(conn, plot_id: str, date_from: date | None = None, date_to: date | None = None) -> dict:
    plot = get_plot(conn, plot_id)
    s = active_season(conn, plot_id)
    date_from = date_from or (date.fromisoformat(s["sowing_date"]) if s else settings.today() - timedelta(days=120))
    date_to = date_to or settings.today()
    sat = satellite.get_images(plot, date_from, date_to)
    if sat is None:
        return {"plot_id": plot_id, "series": [], "mode": None, "available": False,
                "message": "Satellite data not available for this plot."}
    series = valid_series(sat["images"])
    return {"plot_id": plot_id, "series": series, "all_images": len(sat["images"]), "mode": sat["mode"],
            "fixture_kind": sat.get("fixture_kind"), "source": sat["source"], "available": True,
            "message": None if series else "No clear satellite image for this period (clouds)."}


def event_ndvi(conn, event: dict) -> dict:
    plot = get_plot(conn, event["plot_id"])
    ev_date = date.fromisoformat(event["event_date"])
    sat = satellite.get_images(plot, ev_date - timedelta(days=25), ev_date + timedelta(days=25))
    if sat is None:
        return {"available": False, "message": "Satellite data not available for this plot."}
    from models import db
    harvests = [r["entry_date"] for r in db.rows(conn, "SELECT entry_date FROM entry WHERE season_id = ? AND "
                                                       "category = 'harvest' AND deleted = 0", (event["season_id"] or "",))]
    return {"available": True, **ndvi_change(sat["images"], ev_date, harvests), "mode": sat["mode"],
            "fixture_kind": sat.get("fixture_kind")}


def price_for_season(conn, season_id: str) -> dict | None:
    from models import db
    s = db.one(conn, "SELECT s.crop, p.nearest_market FROM season s JOIN plot p ON p.plot_id = s.plot_id "
                     "WHERE s.season_id = ?", (season_id,))
    return mandi.get_price(s["crop"], s["nearest_market"]) if s else None


def metrics_with_extras(conn, season_id: str) -> dict:
    """F4 metrics + benchmark comparison (F17) + projected profit at latest mandi price."""
    from models import db
    from tools.ledger import projected_profit
    from tools.money import change_pct
    m = season_metrics(conn, season_id)
    s = db.one(conn, "SELECT s.*, f.state FROM season s JOIN plot p ON p.plot_id = s.plot_id "
                     "JOIN farmer f ON f.farmer_id = p.farmer_id WHERE s.season_id = ?", (season_id,))
    bench = mandi.get_benchmark(s["crop"], s["state"])
    m["benchmark"] = None
    if bench and m["cost_per_quintal"] is not None:
        m["benchmark"] = {"cost_per_quintal": bench["cost_per_quintal"], "state": bench["state"], "year": bench["year"],
                          "difference_pct": change_pct(m["cost_per_quintal"], bench["cost_per_quintal"]),
                          "source": bench["source"]}
    price = price_for_season(conn, season_id)
    m["price"] = price
    m["projected"] = projected_profit(conn, season_id, price["modal_price"]) if price and m["profit"] is None else None
    return m
