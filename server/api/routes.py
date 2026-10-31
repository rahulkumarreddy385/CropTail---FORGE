"""HTTP API (spec section 4). Handlers stay thin: validation + calls into tools/ and ai/."""
import io
import mimetypes
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import ExifTags, Image, ImageOps
from pydantic import BaseModel, Field

from ai import agent, llm, parser, vision
from config import rules
from config.settings import settings
from models import db
from seed import seed
from services import mandi
from services.http import LAST_MODE, DataUnavailable
from tools import evidence_pack, insights, ledger
from tools import events as ev_tools

router = APIRouter(prefix="/api")


def err(status: int, message: str, **extra):
    raise HTTPException(status_code=status, detail={"message": message, **extra})


NOT_FOUND = "We couldn't find that record. It may have been deleted."


def _plot_or_404(conn, plot_id):
    p = db.one(conn, "SELECT * FROM plot WHERE plot_id = ?", (plot_id,))
    if not p:
        err(404, NOT_FOUND)
    return p


# ---------------- health / farmer / demo ----------------
@router.get("/health")
def health():
    cached = settings.use_cached_data
    return {"status": "ok", "llm": "live" if llm.enabled() else "fallback",
            "weather": "cached" if cached else LAST_MODE.get("weather", "live"),
            "satellite": "cached" if cached or not settings.gee_service_account_json else LAST_MODE.get("satellite", "live"),
            "mandi": "cached" if cached or not (settings.data_gov_in_api_key and settings.mandi_resource_id)
            else LAST_MODE.get("mandi", "live"),
            "simulation_allowed": settings.allow_simulation, "today": settings.today().isoformat()}


@router.get("/farmer")
def get_farmer():
    with db.db() as conn:
        f = db.one(conn, "SELECT * FROM farmer LIMIT 1")
    if not f:
        err(404, NOT_FOUND)
    return f


@router.post("/demo/reset")
def demo_reset():
    return {"ok": True, "counts": seed.reset_db()}


# ---------------- plots & seasons ----------------
class PlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    area_acres: float = Field(gt=0, le=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    survey_number: str | None = Field(default=None, max_length=40)
    nearest_market: str | None = Field(default=None, max_length=60)


class PlotPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    area_acres: float | None = Field(default=None, gt=0, le=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    survey_number: str | None = Field(default=None, max_length=40)
    nearest_market: str | None = Field(default=None, max_length=60)


def _plot_view(conn, p: dict, with_risk: bool) -> dict:
    s = ledger.active_season(conn, p["plot_id"])
    out = {**p, "active_season": s, "stage": None, "season_cost": None, "last_log_date": None, "risk": None}
    if s:
        out["stage"] = ledger.crop_stage(s["crop"], s["sowing_date"], settings.today())
        out["season_cost"] = ledger.season_metrics(conn, s["season_id"])["total_cost"]
        last = db.one(conn, "SELECT MAX(entry_date) AS d FROM entry WHERE season_id = ? AND deleted = 0",
                      (s["season_id"],))
        out["last_log_date"] = last["d"] if last else None
    if with_risk:
        try:
            out["risk"] = insights.plot_risk(conn, p["plot_id"])
        except DataUnavailable as exc:
            out["risk"] = {"level": None, "error": exc.message}
    return out


@router.get("/plots")
def list_plots(include_risk: bool = True):
    with db.db() as conn:
        return [_plot_view(conn, p, include_risk) for p in db.rows(conn, "SELECT * FROM plot ORDER BY created_seq")]


@router.post("/plots", status_code=201)
def create_plot(body: PlotIn):
    with db.db() as conn:
        farmer = db.one(conn, "SELECT farmer_id FROM farmer LIMIT 1")
        seq = conn.execute("SELECT COALESCE(MAX(created_seq), 0) + 1 FROM plot").fetchone()[0]
        p = {"plot_id": db.new_id("P"), "farmer_id": farmer["farmer_id"], **body.model_dump(), "created_seq": seq}
        db.insert(conn, "plot", p)
        return _plot_view(conn, p, False)


@router.get("/plots/{plot_id}")
def get_plot(plot_id: str):
    with db.db() as conn:
        return _plot_view(conn, _plot_or_404(conn, plot_id), True)


@router.patch("/plots/{plot_id}")
def patch_plot(plot_id: str, body: PlotPatch):
    with db.db() as conn:
        _plot_or_404(conn, plot_id)
        db.update(conn, "plot", "plot_id", plot_id, body.model_dump(exclude_unset=True))
        return _plot_view(conn, _plot_or_404(conn, plot_id), False)


class SeasonIn(BaseModel):
    plot_id: str
    crop: Literal["paddy", "wheat", "tomato", "other"]
    season_label: str = Field(min_length=1, max_length=40)
    sowing_date: date
    policy_number: str | None = Field(default=None, max_length=60)


class SeasonPatch(BaseModel):
    season_label: str | None = Field(default=None, min_length=1, max_length=40)
    sowing_date: date | None = None
    status: Literal["active", "closed"] | None = None
    policy_number: str | None = Field(default=None, max_length=60)


@router.get("/seasons")
def list_seasons(plot_id: str | None = None):
    with db.db() as conn:
        if plot_id:
            return db.rows(conn, "SELECT * FROM season WHERE plot_id = ? ORDER BY sowing_date DESC", (plot_id,))
        return db.rows(conn, "SELECT * FROM season ORDER BY sowing_date DESC")


@router.post("/seasons", status_code=201)
def create_season(body: SeasonIn):
    with db.db() as conn:
        _plot_or_404(conn, body.plot_id)
        conn.execute("UPDATE season SET status = 'closed' WHERE plot_id = ? AND status = 'active'", (body.plot_id,))
        s = {"season_id": db.new_id("S"), **body.model_dump(), "sowing_date": body.sowing_date.isoformat(),
             "status": "active"}
        db.insert(conn, "season", s)
        return s


@router.patch("/seasons/{season_id}")
def patch_season(season_id: str, body: SeasonPatch):
    with db.db() as conn:
        s = db.one(conn, "SELECT * FROM season WHERE season_id = ?", (season_id,))
        if not s:
            err(404, NOT_FOUND)
        data = body.model_dump(exclude_unset=True)
        if "sowing_date" in data and data["sowing_date"]:
            data["sowing_date"] = data["sowing_date"].isoformat()
        if data.get("status") == "active":
            conn.execute("UPDATE season SET status = 'closed' WHERE plot_id = ? AND status = 'active'", (s["plot_id"],))
        db.update(conn, "season", "season_id", season_id, data)
        return db.one(conn, "SELECT * FROM season WHERE season_id = ?", (season_id,))


@router.get("/seasons/{season_id}/metrics")
def metrics(season_id: str):
    with db.db() as conn:
        try:
            return insights.metrics_with_extras(conn, season_id)
        except ledger.NotFound:
            err(404, NOT_FOUND)


# ---------------- entries ----------------
class ParseIn(BaseModel):
    text: str = ""


@router.post("/entries/parse")
def parse_entry(body: ParseIn):
    text = (body.text or "").strip()
    if not text:
        err(422, "Please type or say what you did.")
    if len(text) > rules.LOG_TEXT_MAX:
        err(422, "Please keep each log under 500 characters.")
    with db.db() as conn:
        return parser.parse(conn, text)


class EntryIn(BaseModel):
    season_id: str | None = None
    plot_id: str | None = None
    entry_date: date
    category: Literal["sowing", "seed", "land_prep", "fertiliser", "pesticide", "labour", "irrigation", "harvest",
                      "sale", "note"]
    item: str | None = Field(default=None, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: Literal["kg", "bag", "quintal", "litre", "hour", "day", "acre", "none"] | None = None
    cost_inr: float | None = Field(default=None, ge=0)
    price_per_unit_inr: float | None = Field(default=None, ge=0)
    raw_text: str | None = Field(default=None, max_length=500)
    photo_id: str | None = None
    source: Literal["text", "voice", "photo", "form"] = "form"
    logged_by: Literal["farmer", "helper"] = "farmer"
    force: bool = False


class EntryPatch(BaseModel):
    entry_date: date | None = None
    category: Literal["sowing", "seed", "land_prep", "fertiliser", "pesticide", "labour", "irrigation", "harvest",
                      "sale", "note"] | None = None
    item: str | None = Field(default=None, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: Literal["kg", "bag", "quintal", "litre", "hour", "day", "acre", "none"] | None = None
    cost_inr: float | None = Field(default=None, ge=0)


@router.post("/entries", status_code=201)
def create_entry(body: EntryIn):
    with db.db() as conn:
        season_id = body.season_id
        if not season_id and body.plot_id:
            s = ledger.active_season(conn, body.plot_id)
            season_id = s["season_id"] if s else None
        season = db.one(conn, "SELECT s.*, p.name AS plot_name FROM season s JOIN plot p ON p.plot_id = s.plot_id "
                              "WHERE s.season_id = ?", (season_id,)) if season_id else None
        if not season:
            err(422, "Which plot? Please choose the plot for this entry.", fields={"plot_id": "required"})
        if body.category == "sale" and body.cost_inr is None and body.price_per_unit_inr and body.quantity:
            body.cost_inr = round(body.price_per_unit_inr * body.quantity, 2)
        if not body.force:
            since = (settings.now() - timedelta(minutes=rules.DUPLICATE_WINDOW_MINUTES)).isoformat()
            dup = db.one(conn, "SELECT entry_id FROM entry WHERE season_id = ? AND entry_date = ? AND category = ? "
                               "AND COALESCE(item, '') = COALESCE(?, '') AND COALESCE(cost_inr, -1) = COALESCE(?, -1) "
                               "AND deleted = 0 AND created_at >= ?",
                         (season_id, body.entry_date.isoformat(), body.category, body.item, body.cost_inr, since))
            if dup:
                err(409, "This looks like a duplicate of an entry you just saved. Save anyway?",
                    entry_id=dup["entry_id"])
        e = {"entry_id": db.new_id("e"), "season_id": season_id, "entry_date": body.entry_date.isoformat(),
             "category": body.category, "item": body.item, "quantity": body.quantity, "unit": body.unit,
             "cost_inr": body.cost_inr, "price_per_unit_inr": body.price_per_unit_inr, "raw_text": body.raw_text,
             "photo_id": body.photo_id, "source": body.source, "logged_by": body.logged_by, "deleted": 0,
             "created_at": settings.now().isoformat()}
        db.insert(conn, "entry", e)
        return {**e, "plot_name": season["plot_name"], "plot_id": season["plot_id"]}


@router.get("/entries")
def list_entries(season_id: str | None = None, category: str | None = None,
                 date_from: str | None = Query(default=None, alias="from"),
                 date_to: str | None = Query(default=None, alias="to"), ids: str | None = None):
    with db.db() as conn:
        if ids:
            wanted = [i for i in ids.split(",") if i][:200]
            marks = ",".join("?" for _ in wanted)
            entries = db.rows(conn, f"SELECT e.*, s.plot_id, s.crop, s.season_label FROM entry e JOIN season s ON "
                                    f"s.season_id = e.season_id WHERE e.deleted = 0 AND e.entry_id IN ({marks})", wanted)
            out = {"entries": entries, "count": len(entries)}
        else:
            out = ledger.query_ledger(conn, None, season_id, category, date_from, date_to)
        out["entries"].sort(key=lambda e: (e["entry_date"], e["created_at"]), reverse=True)
        return out


@router.patch("/entries/{entry_id}")
def patch_entry(entry_id: str, body: EntryPatch):
    with db.db() as conn:
        if not db.one(conn, "SELECT 1 FROM entry WHERE entry_id = ? AND deleted = 0", (entry_id,)):
            err(404, NOT_FOUND)
        data = body.model_dump(exclude_unset=True)
        if data.get("entry_date"):
            data["entry_date"] = data["entry_date"].isoformat()
        db.update(conn, "entry", "entry_id", entry_id, data)
        return db.one(conn, "SELECT * FROM entry WHERE entry_id = ?", (entry_id,))


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str):
    with db.db() as conn:
        if not db.one(conn, "SELECT 1 FROM entry WHERE entry_id = ? AND deleted = 0", (entry_id,)):
            err(404, NOT_FOUND)
        db.update(conn, "entry", "entry_id", entry_id, {"deleted": 1})
        return {"ok": True, "entry_id": entry_id}


# ---------------- photos ----------------
ALLOWED_PHOTO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".heic": "image/heic",
                 ".heif": "image/heic"}


def _exif(img) -> tuple[datetime | None, float | None, float | None]:
    try:
        ex = img.getexif()
    except Exception:
        return None, None, None
    taken = None
    sub = ex.get_ifd(0x8769) if hasattr(ex, "get_ifd") else {}
    raw = sub.get(0x9003) or ex.get(0x0132)
    if raw:
        try:
            taken = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").replace(tzinfo=settings.timezone)
        except ValueError:
            pass
    lat = lon = None
    try:
        gps = ex.get_ifd(0x8825)
        tag = {v: k for k, v in ExifTags.GPSTAGS.items()}

        def deg(v):
            return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        if gps.get(tag["GPSLatitude"]) and gps.get(tag["GPSLongitude"]):
            lat = deg(gps[tag["GPSLatitude"]]) * (-1 if gps.get(tag["GPSLatitudeRef"]) == "S" else 1)
            lon = deg(gps[tag["GPSLongitude"]]) * (-1 if gps.get(tag["GPSLongitudeRef"]) == "W" else 1)
    except Exception:
        pass
    return taken, lat, lon


@router.post("/photos", status_code=201)
async def upload_photo(file: UploadFile = File(...), season_id: str | None = Form(default=None),
                       plot_id: str | None = Form(default=None), event_id: str | None = Form(default=None)):
    data = await file.read(rules.PHOTO_MAX_BYTES + 1)
    if len(data) > rules.PHOTO_MAX_BYTES:
        err(413, "Please use a photo smaller than 8 MB.")
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    media = ALLOWED_PHOTO.get(ext) or (file.content_type if file.content_type in ALLOWED_PHOTO.values() else None)
    if not media:
        err(415, "Only JPG, PNG or HEIC photos are supported.")
    if not data:
        err(422, "The photo file is empty.")
    with db.db() as conn:
        if event_id:
            ev = ev_tools.get_event(conn, event_id)
            if not ev:
                err(404, NOT_FOUND)
            season_id = season_id or ev["season_id"]
            plot_id = plot_id or ev["plot_id"]
        if not season_id and plot_id:
            s = ledger.active_season(conn, plot_id)
            season_id = s["season_id"] if s else None
        season = db.one(conn, "SELECT * FROM season WHERE season_id = ?", (season_id,)) if season_id else None
        if not season:
            err(422, "Which plot? Please choose the plot for this photo.")
        plot = _plot_or_404(conn, season["plot_id"])
        photo_id = db.new_id("ph")
        folder = settings.upload_dir / "photos"
        folder.mkdir(parents=True, exist_ok=True)
        taken = lat = lon = None
        out_ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic"}[media]
        path = folder / f"{photo_id}{out_ext}"
        if media in ("image/jpeg", "image/png"):
            try:
                img = Image.open(io.BytesIO(data))
                taken, lat, lon = _exif(img)
                clean = ImageOps.exif_transpose(img)
                if media == "image/jpeg":
                    clean.convert("RGB").save(path, "JPEG", quality=88)  # no exif= argument: metadata stripped
                else:
                    clean.save(path, "PNG")
            except Exception:
                err(415, "Only JPG, PNG or HEIC photos are supported.")
        else:
            path.write_bytes(data)  # HEIC kept as uploaded; metadata not read in the MVP
        loc_src = "exif" if lat is not None else "plot_pin"
        tag, conf = vision.tag_photo(str(path), media)
        ph = {"photo_id": photo_id, "season_id": season["season_id"], "event_id": event_id,
              "taken_at": (taken or settings.now()).isoformat(), "lat": lat if lat is not None else plot["lat"],
              "lon": lon if lon is not None else plot["lon"], "location_source": loc_src, "file_path": str(path),
              "vision_tag": tag, "vision_confidence": conf, "is_placeholder": 0}
        db.insert(conn, "photo", ph)
        return {**ph, "file_url": f"/api/photos/{photo_id}/file"}


@router.get("/photos")
def list_photos(season_id: str | None = None, event_id: str | None = None):
    with db.db() as conn:
        if event_id:
            rows = db.rows(conn, "SELECT * FROM photo WHERE event_id = ? ORDER BY taken_at", (event_id,))
        elif season_id:
            rows = db.rows(conn, "SELECT * FROM photo WHERE season_id = ? ORDER BY taken_at", (season_id,))
        else:
            rows = db.rows(conn, "SELECT * FROM photo ORDER BY taken_at DESC LIMIT 50")
    return [{**r, "file_url": f"/api/photos/{r['photo_id']}/file"} for r in rows]


@router.get("/photos/{photo_id}/file")
def photo_file(photo_id: str):
    with db.db() as conn:
        ph = db.one(conn, "SELECT * FROM photo WHERE photo_id = ?", (photo_id,))
    if not ph:
        err(404, NOT_FOUND)
    return FileResponse(ph["file_path"], media_type=mimetypes.guess_type(ph["file_path"])[0] or "image/jpeg")


# ---------------- agent ----------------
class AskIn(BaseModel):
    question: str = ""
    plot_id: str | None = None


@router.post("/agent/ask")
def ask(body: AskIn):
    q = (body.question or "").strip()
    if not q:
        err(422, "Please type or say your question.")
    if len(q) > rules.QUESTION_MAX:
        err(422, "Please keep your question under 300 characters.")
    with db.db() as conn:
        return agent.ask(conn, q, body.plot_id)


# ---------------- climate ----------------
@router.get("/plots/{plot_id}/spray-check")
def spray(plot_id: str, day: date | None = Query(default=None, alias="date")):
    with db.db() as conn:
        _plot_or_404(conn, plot_id)
        try:
            return insights.plot_spray(conn, plot_id, day)
        except DataUnavailable as exc:
            err(503, exc.message)


@router.get("/plots/{plot_id}/risk")
def risk(plot_id: str):
    with db.db() as conn:
        _plot_or_404(conn, plot_id)
        try:
            return insights.plot_risk(conn, plot_id)
        except DataUnavailable as exc:
            err(503, exc.message)


@router.get("/plots/{plot_id}/forecast")
def forecast(plot_id: str, days: int = 5):
    with db.db() as conn:
        _plot_or_404(conn, plot_id)
        try:
            return insights.plot_forecast(conn, plot_id, min(days, 7))
        except DataUnavailable as exc:
            err(503, exc.message)


@router.get("/plots/{plot_id}/ndvi")
def ndvi(plot_id: str, date_from: date | None = Query(default=None, alias="from"),
         date_to: date | None = Query(default=None, alias="to")):
    with db.db() as conn:
        _plot_or_404(conn, plot_id)
        out = insights.plot_ndvi(conn, plot_id, date_from, date_to)
        out["events"] = db.rows(conn, "SELECT event_id, event_date, type FROM event WHERE plot_id = ? AND status != "
                                      "'dismissed'", (plot_id,))
        return out


class SimIn(BaseModel):
    plot_id: str
    date: date
    precipitation_mm: float = Field(ge=0, le=500)


class MonitorIn(BaseModel):
    simulate: SimIn | None = None


@router.post("/monitor/run")
def monitor(body: MonitorIn | None = None):
    with db.db() as conn:
        if body and body.simulate:
            if not settings.allow_simulation:
                err(403, "Simulation is turned off. Set ALLOW_SIMULATION=true for demo rehearsals.")
            _plot_or_404(conn, body.simulate.plot_id)
            db.insert(conn, "simulation", {"sim_id": db.new_id("sim"), "plot_id": body.simulate.plot_id,
                                           "date": body.simulate.date.isoformat(),
                                           "precipitation_mm": body.simulate.precipitation_mm,
                                           "created_at": settings.now().isoformat()})
        return ev_tools.run_monitor(conn)


# ---------------- events & evidence packs ----------------
def _event_view(conn, e: dict) -> dict:
    plot = db.one(conn, "SELECT name FROM plot WHERE plot_id = ?", (e["plot_id"],))
    alert = db.one(conn, "SELECT message FROM alert WHERE event_id = ? ORDER BY created_at DESC LIMIT 1",
                   (e["event_id"],))
    packs = db.rows(conn, "SELECT pack_id, generated_at, past_deadline FROM evidence_pack WHERE event_id = ? "
                          "ORDER BY generated_at DESC", (e["event_id"],))
    return {**e, "plot_name": plot["name"] if plot else None, "alert_message": alert["message"] if alert else None,
            **ev_tools.countdown(e),
            "packs": [{**p, "file_url": f"/api/evidence-packs/{p['pack_id']}/file"} for p in packs]}


class EventIn(BaseModel):
    plot_id: str
    type: Literal["hail", "inundation", "cloudburst", "landslide", "natural_fire", "unseasonal_rain_post_harvest",
                  "other"]
    event_date: date
    farmer_notes: str | None = Field(default=None, max_length=500)
    estimated_loss_quintals: float | None = Field(default=None, ge=0)


class EventPatch(BaseModel):
    action: Literal["confirm", "dismiss"] | None = None
    estimated_loss_quintals: float | None = Field(default=None, ge=0)
    farmer_notes: str | None = Field(default=None, max_length=500)


@router.get("/events")
def list_events(status: str | None = None, plot_id: str | None = None):
    sql, params = "SELECT * FROM event WHERE 1=1", []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if plot_id:
        sql += " AND plot_id = ?"
        params.append(plot_id)
    with db.db() as conn:
        return [_event_view(conn, e) for e in db.rows(conn, sql + " ORDER BY event_date DESC, created_at DESC", params)]


@router.post("/events", status_code=201)
def report_event(body: EventIn):
    if body.event_date > settings.today():
        err(422, "The event date can't be in the future.", fields={"event_date": "future"})
    with db.db() as conn:
        _plot_or_404(conn, body.plot_id)
        e = ev_tools.create_manual(conn, body.plot_id, body.type, body.event_date, body.farmer_notes,
                                   body.estimated_loss_quintals)
        return _event_view(conn, e)


@router.get("/events/{event_id}")
def get_event(event_id: str):
    with db.db() as conn:
        e = ev_tools.get_event(conn, event_id)
        if not e:
            err(404, NOT_FOUND)
        out = _event_view(conn, e)
        plot = _plot_or_404(conn, e["plot_id"])
        ev_date = date.fromisoformat(e["event_date"])
        try:
            obs = ev_tools.observed_for_plot(conn, plot, ev_date - timedelta(days=3), ev_date + timedelta(days=2))
            out["weather"] = {"days": obs["days"], "mode": obs["mode"], "fixture_kind": obs.get("fixture_kind")}
        except DataUnavailable as exc:
            out["weather"] = {"error": exc.message}
        out["ndvi"] = insights.event_ndvi(conn, e)
        out["photos"] = [{**p, "file_url": f"/api/photos/{p['photo_id']}/file"}
                         for p in db.rows(conn, "SELECT * FROM photo WHERE event_id = ? ORDER BY taken_at", (event_id,))]
        return out


@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: EventPatch):
    with db.db() as conn:
        e = ev_tools.get_event(conn, event_id)
        if not e:
            err(404, NOT_FOUND)
        if body.action:
            try:
                ev_tools.transition(conn, event_id, body.action)
            except ev_tools.StateError as exc:
                err(409, exc.message)
        data = body.model_dump(exclude_unset=True, exclude={"action"})
        if data:
            if e["status"] == "dismissed":
                err(409, "This alert was already closed.")
            db.update(conn, "event", "event_id", event_id, data)
        return _event_view(conn, ev_tools.get_event(conn, event_id))


@router.post("/events/{event_id}/evidence-pack")
def make_pack(event_id: str):
    with db.db() as conn:
        e = ev_tools.get_event(conn, event_id)
        if not e:
            err(404, NOT_FOUND)
        if e["status"] != "confirmed":
            err(409, "Confirm the damage first to create an evidence pack.")
        return evidence_pack.generate(conn, event_id)


@router.get("/evidence-packs/{pack_id}/file")
def pack_file(pack_id: str):
    with db.db() as conn:
        p = db.one(conn, "SELECT * FROM evidence_pack WHERE pack_id = ?", (pack_id,))
    if not p:
        err(404, NOT_FOUND)
    return FileResponse(p["file_path"], media_type="application/pdf", filename=f"CropTrail-{pack_id}.pdf")


# ---------------- prices ----------------
@router.get("/mandi-price")
def mandi_price(crop: str, market: str = ""):
    if crop not in rules.CROPS:
        err(422, "Unknown crop.")
    out = mandi.get_price(crop, market)
    if not out:
        err(404, "No price available for this crop.")
    out["stale"] = (settings.today() - date.fromisoformat(out["arrival_date"])).days > rules.MANDI_STALE_DAYS
    return out


@router.get("/benchmarks")
def benchmarks(crop: str, state: str = ""):
    with db.db() as conn:
        state = state or db.one(conn, "SELECT state FROM farmer")["state"]
    out = mandi.get_benchmark(crop, state)
    if not out:
        err(404, "No benchmark for this crop and state.")
    return out
