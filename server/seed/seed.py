"""Demo seed (spec section 5). All people, places, prices and records are fictional."""
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from config.settings import settings
from models import db

FARMER = {"farmer_id": "F1", "name": "Ramesh Kumar", "language": "hi", "phone": None,
          "state": "Uttar Pradesh", "district": "Barabanki", "village": "Rampur"}

PLOTS = [
    {"plot_id": "P1", "farmer_id": "F1", "name": "Ghar wala khet", "area_acres": 0.5, "lat": 26.9260,
     "lon": 81.1850, "survey_number": None, "nearest_market": "Barabanki", "created_seq": 1},
    {"plot_id": "P2", "farmer_id": "F1", "name": "Nahar wala khet", "area_acres": 2.0, "lat": 26.9310,
     "lon": 81.1920, "survey_number": "214/2", "nearest_market": "Barabanki", "created_seq": 2},
]

SEASONS = [
    {"season_id": "S1", "plot_id": "P2", "crop": "paddy", "season_label": "Kharif 2025",
     "sowing_date": "2025-07-02", "status": "closed", "policy_number": None},
    {"season_id": "S2", "plot_id": "P2", "crop": "paddy", "season_label": "Kharif 2026",
     "sowing_date": "2026-07-01", "status": "active", "policy_number": None},
    {"season_id": "S3", "plot_id": "P1", "crop": "tomato", "season_label": "Kharif 2026",
     "sowing_date": "2026-08-20", "status": "active", "policy_number": None},
]

# (season, date, category, item, qty, unit, cost, price_per_unit)
ENTRIES = [
    ("S1", "2025-06-25", "land_prep", "tractor ploughing", 2, "acre", 3000, None),
    ("S1", "2025-06-28", "seed", "paddy seed", 20, "kg", 1200, None),
    ("S1", "2025-07-02", "labour", "transplanting", 10, "day", 6000, None),
    ("S1", "2025-07-05", "fertiliser", "DAP", 2, "bag", 2800, None),
    ("S1", "2025-07-30", "fertiliser", "urea", 4, "bag", 1600, None),
    ("S1", "2025-08-10", "irrigation", "diesel pump", 12, "hour", 2400, None),
    ("S1", "2025-08-25", "pesticide", "insecticide spray", 1, "none", 1500, None),
    ("S1", "2025-10-28", "labour", "harvesting", 1, "none", 4500, None),
    ("S1", "2025-10-30", "harvest", "paddy", 46, "quintal", None, None),
    ("S1", "2025-11-05", "sale", "paddy", 46, "quintal", 105800, 2300),
    ("S2", "2026-06-24", "land_prep", "tractor ploughing", 2, "acre", 3200, None),
    ("S2", "2026-06-27", "seed", "paddy seed", 20, "kg", 1400, None),
    ("S2", "2026-07-01", "labour", "transplanting", 11, "day", 6600, None),
    ("S2", "2026-07-04", "fertiliser", "DAP", 2, "bag", 2800, None),
    ("S2", "2026-07-29", "fertiliser", "urea", 4, "bag", 1800, None),
    ("S2", "2026-08-12", "irrigation", "diesel pump", 15, "hour", 3000, None),
    ("S2", "2026-08-26", "pesticide", "insecticide spray", 1, "none", 1800, None),
    ("S2", "2026-10-22", "labour", "harvesting", 1, "none", 5000, None),
    ("S2", "2026-10-24", "harvest", "paddy", 40, "quintal", None, None),
    ("S2", "2026-10-29", "sale", "paddy sold to local trader", 36, "quintal", 82800, 2300),
    ("S3", "2026-08-18", "seed", "tomato seedlings", 3000, "none", 2000, None),
    ("S3", "2026-08-19", "fertiliser", "FYM", 1, "none", 1500, None),
    ("S3", "2026-08-20", "labour", "transplanting", 5, "day", 2500, None),
    ("S3", "2026-09-05", "land_prep", "staking", 1, "none", 1800, None),
    ("S3", "2026-09-20", "pesticide", "fungicide spray", 1, "none", 900, None),
    ("S3", "2026-09-25", "irrigation", "pump", 4, "hour", 800, None),
    ("S3", "2026-08-25", "labour", "bed mulching and tying", 2, "day", 1400, None),
    ("S3", "2026-09-12", "fertiliser", "soil-test based top dressing", 1, "bag", 1400, None),
    ("S3", "2026-09-28", "irrigation", "pump irrigation", 6, "hour", 1200, None),
    ("S3", "2026-10-04", "labour", "pruning and trellis tying", 2, "day", 1000, None),
    ("S3", "2026-10-10", "irrigation", "pump irrigation", 4, "hour", 800, None),
    ("S3", "2026-10-17", "labour", "sorting and crate preparation", 2, "day", 1200, None),
    ("S3", "2026-10-20", "harvest", "tomato first picking", 6, "quintal", None, None),
    ("S3", "2026-10-23", "sale", "tomato sold at local mandi", 4, "quintal", 10400, 2600),
    ("S3", "2026-10-28", "harvest", "tomato second picking", 5, "quintal", None, None),
    ("S3", "2026-10-30", "sale", "tomato sold at local mandi", 4, "quintal", 10400, 2600),
]


def _placeholder_photo(path, label: str) -> None:
    """Clearly-labelled placeholder images: the seed never pretends to be real field evidence."""
    img = Image.new("RGB", (640, 480), (122, 150, 96))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 300, 640, 480], fill=(110, 140, 165))  # standing water band
    for x in range(0, 640, 22):
        d.line([(x, 300), (x + 30, 220)], fill=(176, 160, 70), width=4)  # lodged stalks
    d.rectangle([0, 0, 640, 60], fill=(30, 30, 30))
    d.text((16, 12), "DEMO PLACEHOLDER PHOTO", fill=(255, 255, 255))
    d.text((16, 34), label, fill=(230, 230, 230))
    img.save(path, "JPEG", quality=80)


def reset_db() -> dict:
    db.init_db()
    with db.db() as conn:
        for table in ("evidence_pack", "alert", "simulation", "photo", "event", "entry", "season", "plot", "farmer"):
            conn.execute(f"DELETE FROM {table}")
        db.insert(conn, "farmer", FARMER)
        for p in PLOTS:
            db.insert(conn, "plot", p)
        for s in SEASONS:
            db.insert(conn, "season", s)
        base = datetime(2026, 1, 1, tzinfo=settings.timezone)
        for i, (sid, d, cat, item, qty, unit, cost, ppu) in enumerate(ENTRIES, start=1):
            db.insert(conn, "entry", {
                "entry_id": f"e{i:02d}", "season_id": sid, "entry_date": d, "category": cat, "item": item,
                "quantity": qty, "unit": unit, "cost_inr": cost, "price_per_unit_inr": ppu, "raw_text": None,
                "photo_id": None, "source": "seed", "logged_by": "farmer", "deleted": 0,
                "created_at": (base + timedelta(minutes=i)).isoformat()})

        ev_date = datetime.fromisoformat(settings.demo_event_date).date()
        deadline = datetime.combine(ev_date, datetime.min.time(), settings.timezone).replace(hour=23, minute=59) \
            + timedelta(hours=settings.report_window_hours)
        confirmed_at = datetime.combine(ev_date + timedelta(days=1), datetime.min.time(), settings.timezone).replace(hour=9)
        db.insert(conn, "event", {
            "event_id": "E1", "plot_id": "P2", "season_id": "S2", "type": "inundation",
            "event_date": ev_date.isoformat(), "status": "confirmed", "trigger": "demo_seed",
            "trigger_detail": f"DEMO SCENARIO (fictional): Heavy-rain event for Nahar wala khet on {ev_date.isoformat()}. "
                             "Not a real weather alert or crop-loss report.",
            "confirmed_at": confirmed_at.isoformat(), "report_deadline": deadline.isoformat(),
            "estimated_loss_quintals": 8, "farmer_notes": "DEMO ONLY: Khet mein paani bhar gaya, dhaan gir gaya",
            "created_at": confirmed_at.isoformat()})
        db.insert(conn, "alert", {
            "alert_id": "A1", "event_id": "E1", "plot_id": "P2", "kind": "demo_scenario",
            "message": f"DEMO SCENARIO (fictional): Heavy rain recorded near Nahar wala khet on "
                       f"{ev_date.strftime('%d %b')}. This is not a real alert.",
            "created_at": confirmed_at.isoformat(), "read": 0})

        photo_dir = settings.upload_dir / "photos"
        photo_dir.mkdir(parents=True, exist_ok=True)
        shots = [(ev_date, 17, 40.0), (ev_date + timedelta(days=1), 8, 10.0), (ev_date + timedelta(days=1), 8, 25.0)]
        for i, (d, hour, minute) in enumerate(shots, start=1):
            pid = f"ph{i}"
            path = photo_dir / f"{pid}.jpg"
            _placeholder_photo(path, f"Seeded demo image {i} for event E1 ({d.isoformat()})")
            taken = datetime.combine(d, datetime.min.time(), settings.timezone).replace(hour=hour, minute=int(minute))
            db.insert(conn, "photo", {
                "photo_id": pid, "season_id": "S2", "event_id": "E1", "taken_at": taken.isoformat(),
                "lat": 26.9311 + i * 0.0001, "lon": 81.1919, "location_source": "plot_pin",
                "file_path": str(path), "vision_tag": None, "vision_confidence": None, "is_placeholder": 1})
    return counts()


def counts() -> dict:
    with db.db() as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("farmer", "plot", "season", "entry", "event", "photo")}


def ensure_seeded() -> None:
    db.init_db()
    with db.db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM farmer").fetchone()[0]
    if n == 0:
        reset_db()
