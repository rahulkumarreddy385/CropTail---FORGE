"""L2 season metrics, season comparison, ledger queries and projected profit. Deterministic only."""
from config.rules import CROP_CALENDAR, ENTRY_CATEGORIES, NON_COST_CATEGORIES
from models import db
from tools.money import change_pct, d, money


class NotFound(Exception):
    pass


def get_season(conn, season_id: str) -> dict:
    s = db.one(conn, "SELECT * FROM season WHERE season_id = ?", (season_id,))
    if not s:
        raise NotFound(season_id)
    return s


def get_plot(conn, plot_id: str) -> dict:
    p = db.one(conn, "SELECT * FROM plot WHERE plot_id = ?", (plot_id,))
    if not p:
        raise NotFound(plot_id)
    return p


def active_season(conn, plot_id: str) -> dict | None:
    return db.one(conn, "SELECT * FROM season WHERE plot_id = ? AND status = 'active' ORDER BY sowing_date DESC LIMIT 1",
                  (plot_id,))


def season_entries(conn, season_id: str) -> list[dict]:
    return db.rows(conn, "SELECT * FROM entry WHERE season_id = ? AND deleted = 0 ORDER BY entry_date, created_at",
                   (season_id,))


def season_metrics(conn, season_id: str) -> dict:
    get_season(conn, season_id)
    entries = season_entries(conn, season_id)
    by_cat: dict[str, object] = {}
    total = d(0)
    harvest_q = d(0)
    revenue = d(0)
    has_sale = False
    for e in entries:
        cat = e["category"]
        if cat not in NON_COST_CATEGORIES and e["cost_inr"] is not None:
            total += d(e["cost_inr"])
            by_cat[cat] = by_cat.get(cat, d(0)) + d(e["cost_inr"])
        if cat == "harvest" and e["quantity"] is not None:
            q = d(e["quantity"])
            harvest_q += q / 100 if e["unit"] == "kg" else q
        if cat == "sale":
            has_sale = True
            revenue += d(e["cost_inr"])
    cpq = money(total / harvest_q) if harvest_q > 0 else None
    return {
        "season_id": season_id,
        "total_cost": money(total),
        "cost_by_category": {k: money(v) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "harvest_quintals": float(harvest_q) if harvest_q % 1 else int(harvest_q),
        "cost_per_quintal": cpq,
        "revenue": money(revenue),
        "profit": money(revenue - total) if has_sale else None,
        "entry_count": len(entries),
    }


def projected_profit(conn, season_id: str, price: float) -> dict:
    m = season_metrics(conn, season_id)
    if not m["harvest_quintals"]:
        return {"season_id": season_id, "price": price, "projected_profit": None,
                "reason": "No harvest quantity recorded yet."}
    value = money(d(m["harvest_quintals"]) * d(price) - d(m["total_cost"]))
    return {"season_id": season_id, "price": money(price), "harvest_quintals": m["harvest_quintals"],
            "total_cost": m["total_cost"], "revenue_at_price": money(d(m["harvest_quintals"]) * d(price)),
            "projected_profit": value}


def _metric_value(m: dict, metric: str):
    if metric in ENTRY_CATEGORIES:
        return m["cost_by_category"].get(metric, 0.0)
    return m.get(metric)


def compare_seasons(conn, plot_id: str, crop: str, metric: str) -> dict:
    """Active season of `crop` on the plot vs the most recent closed season of the same crop."""
    get_plot(conn, plot_id)
    cur = db.one(conn, "SELECT * FROM season WHERE plot_id = ? AND crop = ? AND status = 'active' "
                       "ORDER BY sowing_date DESC LIMIT 1", (plot_id, crop))
    if not cur:
        return {"metric": metric, "current": None, "previous": None, "change_pct": None,
                "reason": "No active season of this crop on this plot."}
    prev = db.one(conn, "SELECT * FROM season WHERE plot_id = ? AND crop = ? AND status = 'closed' "
                        "AND sowing_date < ? ORDER BY sowing_date DESC LIMIT 1", (plot_id, crop, cur["sowing_date"]))
    cur_v = _metric_value(season_metrics(conn, cur["season_id"]), metric)
    if not prev:
        return {"metric": metric, "current": cur_v, "previous": None, "change_pct": None,
                "current_season": cur["season_label"], "previous_season": None,
                "reason": "No earlier season of this crop on this plot to compare with."}
    prev_v = _metric_value(season_metrics(conn, prev["season_id"]), metric)
    return {"metric": metric, "current": cur_v, "previous": prev_v, "change_pct": change_pct(cur_v, prev_v),
            "current_season": cur["season_label"], "previous_season": prev["season_label"],
            "current_season_id": cur["season_id"], "previous_season_id": prev["season_id"]}


def query_ledger(conn, plot_id: str | None = None, season_id: str | None = None, category: str | None = None,
                 date_from: str | None = None, date_to: str | None = None, item_like: str | None = None) -> dict:
    sql = ("SELECT e.*, s.plot_id, s.crop, s.season_label FROM entry e JOIN season s ON s.season_id = e.season_id "
           "WHERE e.deleted = 0")
    params: list = []
    for col, val in (("s.plot_id", plot_id), ("e.season_id", season_id), ("e.category", category)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    if date_from:
        sql += " AND e.entry_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND e.entry_date <= ?"
        params.append(date_to)
    if item_like:
        sql += " AND LOWER(COALESCE(e.item,'') || ' ' || COALESCE(e.raw_text,'')) LIKE ?"
        params.append(f"%{item_like.lower()}%")
    sql += " ORDER BY e.entry_date, e.created_at"
    entries = db.rows(conn, sql, params)
    total = sum(d(e["cost_inr"]) for e in entries if e["category"] not in NON_COST_CATEGORIES and e["cost_inr"])
    return {"entries": entries, "count": len(entries), "total_cost": money(total)}


def crop_stage(crop: str, sowing_date: str, today) -> dict:
    """L4 crop stage from days since sowing/transplanting."""
    from datetime import date
    days = (today - date.fromisoformat(sowing_date)).days
    for stage, lo, hi in CROP_CALENDAR.get(crop, []):
        if days >= lo and (hi is None or days <= hi):
            return {"stage": stage, "days": days}
    return {"stage": "unknown", "days": days}
