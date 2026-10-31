"""L6 weather monitor and L7 event state machine."""
from datetime import date, datetime, timedelta

from config import rules
from config.settings import settings
from models import db
from services import weather
from tools.ledger import active_season, crop_stage, get_plot


class StateError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def report_deadline(event_date: date) -> datetime:
    end_of_day = datetime.combine(event_date, datetime.min.time(), settings.timezone).replace(hour=23, minute=59)
    return end_of_day + timedelta(hours=settings.report_window_hours)


def observed_for_plot(conn, plot: dict, start: date, end: date) -> dict:
    """Observed weather for a plot, with any demo simulations clearly flagged."""
    obs = weather.get_observed(plot["lat"], plot["lon"], start, end)
    sims = db.rows(conn, "SELECT * FROM simulation WHERE plot_id = ? AND date BETWEEN ? AND ?",
                   (plot["plot_id"], start.isoformat(), end.isoformat()))
    sim_by_date = {s["date"]: s for s in sims}
    days = []
    for x in obs["days"]:
        x = dict(x, simulated=False)
        if x["date"] in sim_by_date:
            x.update(precipitation_sum=sim_by_date[x["date"]]["precipitation_mm"], simulated=True)
        days.append(x)
    return {**obs, "days": days}


def _event_type(conn, season: dict, day: date, code) -> str:
    if code in rules.HAIL_WEATHER_CODES:
        return "hail"
    stage = crop_stage(season["crop"], season["sowing_date"], day)["stage"]
    recent_harvest = db.one(conn, "SELECT 1 FROM entry WHERE season_id = ? AND category = 'harvest' AND deleted = 0 "
                                  "AND entry_date BETWEEN ? AND ?",
                            (season["season_id"], (day - timedelta(days=rules.POST_HARVEST_WINDOW_DAYS)).isoformat(),
                             day.isoformat()))
    return "unseasonal_rain_post_harvest" if stage == "harvest_ready" or recent_harvest else "inundation"


def run_monitor(conn) -> dict:
    today = settings.today()
    start = today - timedelta(days=rules.MONITOR_LOOKBACK_DAYS)
    plots = db.rows(conn, "SELECT p.* FROM plot p WHERE EXISTS (SELECT 1 FROM season s WHERE s.plot_id = p.plot_id "
                          "AND s.status = 'active') ORDER BY created_seq")
    new_events, skipped, mode, errors = [], [], None, []
    for plot in plots:
        season = active_season(conn, plot["plot_id"])
        try:
            obs = observed_for_plot(conn, plot, start, today)
        except weather.DataUnavailable as exc:
            errors.append({"plot_id": plot["plot_id"], "message": exc.message})
            continue
        mode = obs["mode"] if mode in (None, "live") else mode
        for x in obs["days"]:
            rain = x["precipitation_sum"]
            hail = x.get("weather_code") in rules.HAIL_WEATHER_CODES
            if not hail and (rain is None or rain < settings.heavy_rain_mm):
                continue
            day = date.fromisoformat(x["date"])
            lo = (day - timedelta(days=rules.MONITOR_DEDUPE_DAYS)).isoformat()
            hi = (day + timedelta(days=rules.MONITOR_DEDUPE_DAYS)).isoformat()
            dup = db.one(conn, "SELECT event_id FROM event WHERE plot_id = ? AND status != 'dismissed' "
                               "AND event_date BETWEEN ? AND ?", (plot["plot_id"], lo, hi))
            if dup:
                skipped.append({"plot_id": plot["plot_id"], "date": x["date"], "reason": "skipped_duplicate",
                                "existing_event_id": dup["event_id"]})
                continue
            etype = _event_type(conn, season, day, x.get("weather_code"))
            sim = "[SIMULATED FOR DEMO] " if x.get("simulated") else ""
            what = "Thunderstorm with hail" if hail else f"Observed rainfall {rain:g} mm"
            event = {
                "event_id": db.new_id("E"), "plot_id": plot["plot_id"], "season_id": season["season_id"],
                "type": etype, "event_date": x["date"], "status": "suspected", "trigger": "auto_weather",
                "trigger_detail": f"{sim}{what} on {x['date']}", "confirmed_at": None,
                "report_deadline": report_deadline(day).isoformat(), "estimated_loss_quintals": None,
                "farmer_notes": None, "created_at": settings.now().isoformat()}
            db.insert(conn, "event", event)
            heavy = f"Heavy rain ({rain:g} mm)" if not hail else "Hail"
            msg = (f"{'[Simulated] ' if x.get('simulated') else ''}{heavy} recorded near {plot['name']} on {day.strftime('%d %b')}. "
                   "Was your crop damaged? Confirm and add photos.")
            db.insert(conn, "alert", {"alert_id": db.new_id("A"), "event_id": event["event_id"],
                                      "plot_id": plot["plot_id"], "kind": "loss_event", "message": msg,
                                      "created_at": settings.now().isoformat(), "read": 0})
            new_events.append({**event, "alert_message": msg})
    return {"checked_plots": len(plots), "new_events": new_events, "skipped": skipped,
            "errors": errors, "mode": mode or "live"}


def get_event(conn, event_id: str) -> dict | None:
    return db.one(conn, "SELECT * FROM event WHERE event_id = ?", (event_id,))


def transition(conn, event_id: str, action: str) -> dict:
    ev = get_event(conn, event_id)
    if not ev:
        raise LookupError(event_id)
    if ev["status"] != "suspected":
        raise StateError("This alert was already closed.")
    now = settings.now().isoformat()
    if action == "confirm":
        db.update(conn, "event", "event_id", event_id, {"status": "confirmed", "confirmed_at": now})
    elif action == "dismiss":
        db.update(conn, "event", "event_id", event_id, {"status": "dismissed"})
    conn.execute("UPDATE alert SET read = 1 WHERE event_id = ?", (event_id,))
    return get_event(conn, event_id)


def create_manual(conn, plot_id: str, etype: str, event_date: date, notes: str | None,
                  loss_q: float | None) -> dict:
    plot = get_plot(conn, plot_id)
    season = active_season(conn, plot_id)
    now = settings.now().isoformat()
    ev = {"event_id": db.new_id("E"), "plot_id": plot["plot_id"], "season_id": season["season_id"] if season else None,
          "type": etype, "event_date": event_date.isoformat(), "status": "confirmed", "trigger": "manual",
          "trigger_detail": f"Reported by farmer for {event_date.isoformat()}", "confirmed_at": now,
          "report_deadline": report_deadline(event_date).isoformat(), "estimated_loss_quintals": loss_q,
          "farmer_notes": notes, "created_at": now}
    db.insert(conn, "event", ev)
    return ev


def countdown(ev: dict) -> dict:
    deadline = datetime.fromisoformat(ev["report_deadline"])
    seconds = int((deadline - settings.now()).total_seconds())
    return {"seconds_left": max(seconds, 0), "past_deadline": seconds <= 0}
