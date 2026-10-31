"""Allowlisted agent tools (L10). Each has a JSON schema; arguments are validated before running."""
from datetime import date

from config import rules
from config.settings import settings
from models import db
from services import mandi, weather
from tools import events as ev_tools
from tools import insights, ledger

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, properties: dict, required: list[str]):
    def wrap(fn):
        TOOLS[name] = {"fn": fn, "schema": {"name": name, "description": description,
                                             "input_schema": {"type": "object", "properties": properties,
                                                              "required": required, "additionalProperties": False}}}
        return fn
    return wrap


S = {"type": "string"}
DATE = {"type": "string", "description": "YYYY-MM-DD"}


class ToolArgError(Exception):
    pass


def validate(name: str, args: dict) -> dict:
    if name not in TOOLS:
        raise ToolArgError(f"Unknown tool {name}")
    schema = TOOLS[name]["schema"]["input_schema"]
    props = schema["properties"]
    for k in args:
        if k not in props:
            raise ToolArgError(f"Unknown argument {k}")
    for k in schema["required"]:
        if args.get(k) in (None, ""):
            raise ToolArgError(f"Missing argument {k}")
    clean = {}
    for k, v in args.items():
        p = props[k]
        if v is None:
            continue
        if p.get("type") == "integer":
            if not isinstance(v, int):
                raise ToolArgError(f"{k} must be an integer")
            if "maximum" in p and v > p["maximum"]:
                raise ToolArgError(f"{k} must be <= {p['maximum']}")
        elif p.get("type") == "number":
            if not isinstance(v, (int, float)):
                raise ToolArgError(f"{k} must be a number")
        elif not isinstance(v, str):
            raise ToolArgError(f"{k} must be a string")
        if "enum" in p and v not in p["enum"]:
            raise ToolArgError(f"{k} must be one of {p['enum']}")
        if p is DATE or p.get("description") == "YYYY-MM-DD":
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise ToolArgError(f"{k} must be YYYY-MM-DD") from exc
        clean[k] = v
    return clean


def run(conn, name: str, args: dict) -> dict:
    clean = validate(name, args or {})
    return TOOLS[name]["fn"](conn, **clean)


def _d(s):
    return date.fromisoformat(s) if s else None


@tool("query_ledger", "List the farmer's ledger entries with optional filters. Returns entries and the total cost.",
      {"plot_id": S, "season_id": S, "category": {"type": "string", "enum": rules.ENTRY_CATEGORIES},
       "from": DATE, "to": DATE, "item": {"type": "string", "description": "text to search in item names"}}, [])
def t_query_ledger(conn, plot_id=None, season_id=None, category=None, item=None, **kw):
    out = ledger.query_ledger(conn, plot_id, season_id, category, kw.get("from"), kw.get("to"), item)
    out["_source"] = {"type": "ledger", "label": f"Ledger: {out['count']} entries",
                      "ref": [e["entry_id"] for e in out["entries"]]}
    return out


@tool("get_season_metrics", "Totals for a season: total cost, cost by category, harvest quintals, cost per quintal, "
      "revenue, profit, benchmark.", {"season_id": S}, ["season_id"])
def t_metrics(conn, season_id):
    out = insights.metrics_with_extras(conn, season_id)
    ids = [e["entry_id"] for e in ledger.season_entries(conn, season_id)]
    out["_source"] = {"type": "ledger", "label": f"Ledger: {len(ids)} entries", "ref": ids}
    return out


@tool("compare_seasons", "Compare the active season of a crop on a plot with its previous closed season. metric is "
      "total_cost, cost_per_quintal, harvest_quintals, revenue or an entry category such as fertiliser.",
      {"plot_id": S, "crop": {"type": "string", "enum": rules.CROPS},
       "metric": {"type": "string", "enum": ["total_cost", "cost_per_quintal", "harvest_quintals", "revenue"]
                  + rules.ENTRY_CATEGORIES}}, ["plot_id", "crop", "metric"])
def t_compare(conn, plot_id, crop, metric):
    out = ledger.compare_seasons(conn, plot_id, crop, metric)
    ids = []
    for sid in (out.get("current_season_id"), out.get("previous_season_id")):
        if sid:
            ids += [e["entry_id"] for e in ledger.season_entries(conn, sid)
                    if metric not in rules.ENTRY_CATEGORIES or e["category"] == metric]
    out["_source"] = {"type": "ledger", "label": f"Ledger: {len(ids)} entries", "ref": ids}
    return out


@tool("get_forecast", "Daily weather forecast for a plot (rain, max temperature, gusts).",
      {"plot_id": S, "days": {"type": "integer", "maximum": 7}}, ["plot_id"])
def t_forecast(conn, plot_id, days=5):
    out = insights.plot_forecast(conn, plot_id, days)
    out["_source"] = {"type": "forecast", "label": f"Forecast: Open-Meteo {out['fetched_at'][:16].replace('T', ' ')}",
                      "ref": plot_id, "mode": out["mode"]}
    return out


@tool("spray_check", "Rule-based check whether spraying is advisable on a date (default tomorrow) from the hourly "
      "forecast. Never gives products or doses.", {"plot_id": S, "date": DATE}, ["plot_id"])
def t_spray(conn, plot_id, date=None):
    out = insights.plot_spray(conn, plot_id, _d(date))
    out["_source"] = {"type": "forecast", "label": f"Forecast: Open-Meteo {out['forecast_fetched_at'][:16].replace('T', ' ')}",
                      "ref": plot_id, "mode": out["mode"]}
    return out


@tool("get_plot_risk", "Low/medium/high weather risk for the next 5 days for a plot, using crop stage.",
      {"plot_id": S}, ["plot_id"])
def t_risk(conn, plot_id):
    out = insights.plot_risk(conn, plot_id)
    out["_source"] = {"type": "forecast", "label": "Risk: forecast + crop stage", "ref": plot_id, "mode": out["mode"]}
    return out


@tool("get_weather_history", "Observed daily weather for a plot between two dates.",
      {"plot_id": S, "from": DATE, "to": DATE}, ["plot_id", "from", "to"])
def t_history(conn, plot_id, **kw):
    plot = ledger.get_plot(conn, plot_id)
    out = ev_tools.observed_for_plot(conn, plot, _d(kw["from"]), _d(kw["to"]))
    out["_source"] = {"type": "weather", "label": f"Observed weather: {out['source']}", "ref": plot_id,
                      "mode": out["mode"]}
    return out


@tool("get_ndvi", "Sentinel-2 NDVI series (crop greenness 0-1) for a plot.", {"plot_id": S, "from": DATE, "to": DATE},
      ["plot_id"])
def t_ndvi(conn, plot_id, **kw):
    out = insights.plot_ndvi(conn, plot_id, _d(kw.get("from")), _d(kw.get("to")))
    out["_source"] = {"type": "satellite", "label": "Satellite: Sentinel-2 NDVI", "ref": plot_id, "mode": out["mode"]}
    return out


@tool("get_mandi_price", "Latest modal mandi price in rupees per quintal.",
      {"crop": {"type": "string", "enum": rules.CROPS}, "market": S}, ["crop"])
def t_price(conn, crop, market=None):
    if not market:
        f = db.one(conn, "SELECT nearest_market FROM plot WHERE nearest_market IS NOT NULL ORDER BY created_seq")
        market = f["nearest_market"] if f else ""
    out = mandi.get_price(crop, market) or {"crop": crop, "modal_price": None, "message": "No price available."}
    out["_source"] = {"type": "mandi", "label": f"Mandi: {out.get('market', market)} {out.get('arrival_date', '')}".strip(),
                      "ref": crop, "mode": out.get("mode")}
    return out


@tool("get_benchmark", "Official average cost of cultivation per quintal for a crop in a state.",
      {"crop": {"type": "string", "enum": rules.CROPS}, "state": S}, ["crop"])
def t_bench(conn, crop, state=None):
    if not state:
        state = db.one(conn, "SELECT state FROM farmer")["state"]
    out = mandi.get_benchmark(crop, state) or {"crop": crop, "cost_per_quintal": None, "message": "No benchmark."}
    out["_source"] = {"type": "benchmark", "label": f"Benchmark: {out.get('source', 'n/a')}", "ref": crop}
    return out


@tool("projected_profit", "Profit for a season if the harvest sells at a price (default: latest mandi price).",
      {"season_id": S, "price": {"type": "number"}}, ["season_id"])
def t_profit(conn, season_id, price=None):
    p = None
    if price is None:
        p = insights.price_for_season(conn, season_id)
        if not p:
            return {"projected_profit": None, "message": "No mandi price available."}
        price = p["modal_price"]
    out = ledger.projected_profit(conn, season_id, price)
    out["price_source"] = p
    ids = [e["entry_id"] for e in ledger.season_entries(conn, season_id)]
    out["_source"] = {"type": "ledger", "label": f"Ledger: {len(ids)} entries", "ref": ids}
    return out


@tool("list_events", "Loss events (suspected, confirmed, dismissed) for a plot or all plots.", {"plot_id": S}, [])
def t_events(conn, plot_id=None):
    sql, params = "SELECT * FROM event", ()
    if plot_id:
        sql, params = sql + " WHERE plot_id = ?", (plot_id,)
    evs = db.rows(conn, sql + " ORDER BY event_date DESC", params)
    return {"events": evs, "_source": {"type": "event", "label": f"Events: {len(evs)}", "ref": [e["event_id"] for e in evs]}}


@tool("generate_evidence_pack", "Prepare the claim evidence PDF for a CONFIRMED event. The user must tap to confirm "
      "before it is generated; this tool only queues that confirmation.", {"event_id": S}, ["event_id"])
def t_pack(conn, event_id):
    e = ev_tools.get_event(conn, event_id)
    if not e:
        return {"ok": False, "message": "No such event."}
    if e["status"] != "confirmed":
        return {"ok": False, "message": "Confirm the damage first to create an evidence pack."}
    return {"ok": True, "requires_confirmation": True,
            "pending_action": {"type": "generate_evidence_pack", "event_id": event_id},
            "_source": {"type": "event", "label": f"Event {event_id} ({e['event_date']})", "ref": event_id}}


def context_summary(conn) -> str:
    """Plot/season ids the agent may use. Plain data for the system prompt."""
    lines = []
    for p in db.rows(conn, "SELECT * FROM plot ORDER BY created_seq"):
        seasons = db.rows(conn, "SELECT season_id, crop, season_label, sowing_date, status FROM season "
                                "WHERE plot_id = ? ORDER BY sowing_date", (p["plot_id"],))
        ss = "; ".join(f"{s['season_id']} {s['crop']} {s['season_label']} sown {s['sowing_date']} ({s['status']})"
                       for s in seasons)
        lines.append(f"- plot {p['created_seq']}: plot_id={p['plot_id']} name=\"{p['name']}\" {p['area_acres']:g} acres, "
                     f"market {p['nearest_market']}. Seasons: {ss}")
    return f"Today is {settings.today().isoformat()}.\n" + "\n".join(lines)
