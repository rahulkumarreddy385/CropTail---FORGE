"""Acceptance criteria (spec section 10), fallback mode with a fixed clock of 2026-10-30 10:00 IST."""
import io
import re
from datetime import date, timedelta

from PIL import Image
from pypdf import PdfReader
import pytest

from tests.conftest import hourly_fixture

TOMORROW = date(2026, 10, 31)


# ---------- AC1-AC2 ----------
def test_health_fallback(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["llm"] == "fallback"
    assert body["weather"] == body["satellite"] == body["mandi"] == "cached"
    assert body["sample_data_enabled"] is True
    assert body["demo_seed_loaded"] is True


def test_hosted_password_login_protects_api(client, monkeypatch):
    from api.routes import LOGIN_FAILURES

    monkeypatch.setenv("APP_PASSWORD", "a-strong-demo-password")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-that-is-long-enough-for-tests")
    monkeypatch.setenv("APP_ENV", "production")
    LOGIN_FAILURES.clear()

    assert client.get("/api/auth/session").json() == {"auth_required": True, "authenticated": False}
    assert client.get("/api/plots").status_code == 401
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401

    response = client.post("/api/auth/login", json={"password": "a-strong-demo-password"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    token = response.cookies["croptrail_session"]
    cookie_header = {"cookie": f"croptrail_session={token}"}
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert client.get("/api/auth/session", headers=cookie_header).json() == {
        "auth_required": True, "authenticated": True,
    }
    assert client.get("/api/plots", headers=cookie_header).status_code == 200

    assert client.post("/api/auth/logout", headers=cookie_header).status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is False
    assert client.get("/api/plots").status_code == 401


def test_production_requires_strong_auth_settings(monkeypatch):
    from main import _normalize_origin, validate_production_config

    assert _normalize_origin("croptrail-client.onrender.com") == "https://croptrail-client.onrender.com"
    assert _normalize_origin("http://localhost:3000") == "http://localhost:3000"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_PASSWORD", "")
    monkeypatch.setenv("SESSION_SECRET", "")
    with pytest.raises(RuntimeError, match="APP_PASSWORD and SESSION_SECRET"):
        validate_production_config()

    monkeypatch.setenv("APP_PASSWORD", "short")
    monkeypatch.setenv("SESSION_SECRET", "short")
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        validate_production_config()

    monkeypatch.setenv("APP_PASSWORD", "a-strong-demo-password")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-that-is-long-enough-for-tests")
    validate_production_config()


def test_hosted_login_rate_limits_failed_passwords(client, monkeypatch):
    from api.routes import LOGIN_FAILURES

    monkeypatch.setenv("APP_PASSWORD", "a-strong-demo-password")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-that-is-long-enough-for-tests")
    LOGIN_FAILURES.clear()

    for _ in range(5):
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/auth/login", json={"password": "a-strong-demo-password"})
    assert response.status_code == 429


def test_reset_counts(client):
    r = client.post("/api/demo/reset")
    c = r.json()["counts"]
    assert (c["farmer"], c["plot"], c["season"], c["entry"], c["event"]) == (1, 2, 3, 36, 1)
    ev = client.get("/api/events/E1").json()
    assert ev["status"] == "confirmed" and ev["is_demo"] is True
    assert ev["trigger"] == "demo_seed"
    assert all(p["is_placeholder"] for p in ev["photos"])


# ---------- AC3-AC8 metrics ----------
def test_season_metrics_s1(client):
    m = client.get("/api/seasons/S1/metrics").json()
    assert m["total_cost"] == 23000.00 and m["harvest_quintals"] == 46
    assert m["cost_per_quintal"] == 500.00 and m["revenue"] == 105800.00 and m["profit"] == 82800.00


def test_season_metrics_s2(client):
    m = client.get("/api/seasons/S2/metrics").json()
    assert m["total_cost"] == 25600.00 and m["harvest_quintals"] == 40 and m["cost_per_quintal"] == 640.00
    assert m["revenue"] == 82800.00 and m["profit"] == 57200.00
    assert m["cost_by_category"]["fertiliser"] == 4600.00


def test_cost_per_quintal_null_without_harvest(client):
    season = client.post("/api/seasons", json={"plot_id": "P1", "crop": "tomato",
                                               "season_label": "Test season", "sowing_date": "2026-10-30"}).json()
    client.post("/api/entries", json={"season_id": season["season_id"], "entry_date": "2026-10-30",
                                     "category": "fertiliser", "item": "compost", "cost_inr": 9500})
    m = client.get(f"/api/seasons/{season['season_id']}/metrics").json()
    assert m["total_cost"] == 9500.00 and m["cost_per_quintal"] is None


def test_tomato_demo_has_partial_harvest_and_sales(client):
    m = client.get("/api/seasons/S3/metrics").json()
    assert m["total_cost"] == 16500.00
    assert m["harvest_quintals"] == 11
    assert m["cost_per_quintal"] == 1500.00
    assert m["revenue"] == 20800.00
    assert m["profit"] == 4300.00


def test_compare_seasons_fertiliser(conn):
    from tools.ledger import compare_seasons
    out = compare_seasons(conn, "P2", "paddy", "fertiliser")
    assert (out["current"], out["previous"], out["change_pct"]) == (4600.00, 4400.00, 4.5)
    out = compare_seasons(conn, "P2", "paddy", "cost_per_quintal")
    assert (out["current"], out["previous"], out["change_pct"]) == (640.00, 500.00, 28.0)


def test_projected_profit(conn):
    from tools.ledger import projected_profit
    assert projected_profit(conn, "S2", 2300)["projected_profit"] == 66400.00


# ---------- AC9, SC1 parsing ----------
def test_fallback_parser_urea_hindi(client):
    r = client.post("/api/entries/parse", json={"text": "Plot 2 mein 2 bag urea dala ₹900"}).json()
    d = r["draft"]
    assert (d["category"], d["item"], d["quantity"], d["unit"], d["cost_inr"]) == ("fertiliser", "urea", 2, "bag", 900.0)
    assert r["resolved_plot_id"] == "P2" and d["entry_date"] == "2026-10-30" and r["mode"] == "fallback"
    assert client.post("/api/demo/reset").json()["counts"]["entry"] == 36  # nothing saved by parse


def test_relative_date_kal(client):
    r = client.post("/api/entries/parse", json={"text": "kal plot 1 par 4 ghante paani diya ₹800"}).json()
    d = r["draft"]
    assert d["entry_date"] == "2026-10-29" and d["category"] == "irrigation" and d["cost_inr"] == 800
    assert r["resolved_plot_id"] == "P1"
    save = client.post("/api/entries", json={"plot_id": "P1", "entry_date": d["entry_date"], "category": d["category"],
                                             "quantity": d["quantity"], "unit": d["unit"], "cost_inr": d["cost_inr"],
                                             "source": "text"})
    assert save.status_code == 201
    assert client.get("/api/seasons/S3/metrics").json()["total_cost"] == 17300.00
    entries = client.get("/api/entries", params={"season_id": "S3"}).json()["entries"]
    assert any(e["category"] == "irrigation" and e["entry_date"] == "2026-10-29" for e in entries)


def test_parse_errors(client):
    assert client.post("/api/entries/parse", json={"text": "  "}).json()["detail"]["message"] == \
        "Please type or say what you did."
    assert client.post("/api/entries/parse", json={"text": "x" * 501}).status_code == 422


def test_english_example(client):
    d = client.post("/api/entries/parse", json={"text": "Sowed wheat on plot 2, 50 kg DAP, ₹1,400"}).json()["draft"]
    assert (d["category"], d["item"], d["quantity"], d["unit"], d["cost_inr"]) == ("fertiliser", "DAP", 50, "kg", 1400)


# ---------- AC10 spray ----------
def test_spray_check_rain():
    from tools.climate import spray_check
    out = spray_check(hourly_fixture(TOMORROW, rain_at=14, rain_mm=3.2), TOMORROW, 24)
    assert out["verdict"] == "not_advised" and any("Rain" in r for r in out["reasons"])


def test_spray_check_ok():
    from tools.climate import spray_check
    out = spray_check(hourly_fixture(TOMORROW, wind=8.0), TOMORROW, 24)
    assert out["verdict"] == "ok" and out["best_window"] is not None


def test_spray_endpoint_uses_fixture(client):
    out = client.get("/api/plots/P1/spray-check").json()
    assert out["verdict"] == "not_advised" and out["mode"] == "cached"


# ---------- AC11 risk / crop stage ----------
def _daily(rain):
    return [{"date": (date(2026, 10, 30) + timedelta(days=i)).isoformat(), "precipitation_sum": rain if i == 2 else 0,
             "temperature_2m_max": 30, "wind_gusts_10m_max": 15, "weather_code": 1} for i in range(6)]


def test_risk_high_sensitive_stage():
    from tools.climate import risk_score
    out = risk_score(_daily(82), "harvest_ready", date(2026, 10, 30))
    assert (out["raw_score"], out["score"], out["level"]) == (3, 4, "high")
    assert risk_score(_daily(82), "vegetative", date(2026, 10, 30))["level"] == "medium"


def test_crop_stage_paddy():
    from tools.ledger import crop_stage
    assert crop_stage("paddy", "2026-07-01", date(2026, 10, 30))["stage"] == "harvest_ready"
    assert crop_stage("paddy", "2026-07-01", date(2026, 8, 30))["stage"] == "flowering"
    assert crop_stage("tomato", "2026-08-20", date(2026, 10, 30))["stage"] == "fruiting"


# ---------- AC12-AC13 monitor & events ----------
def _obs_patch(monkeypatch, plot_mm: dict):
    from services import weather

    def fake(lat, lon, start, end):
        days, d = [], start
        while d <= end:
            mm = plot_mm.get((round(lat, 4), d.isoformat()), 0.0)
            days.append({"date": d.isoformat(), "precipitation_sum": mm, "temperature_2m_max": 29, "weather_code": 63})
            d += timedelta(days=1)
        return {"days": days, "mode": "cached", "fixture_kind": "test", "fetched_at": "2026-10-30T10:00",
                "source": "test"}
    monkeypatch.setattr(weather, "get_observed", fake)


def test_monitor_creates_and_dedupes(client, monkeypatch):
    _obs_patch(monkeypatch, {(26.926, "2026-10-28"): 78.4})
    out = client.post("/api/monitor/run").json()
    assert len(out["new_events"]) == 1
    ev = out["new_events"][0]
    assert ev["plot_id"] == "P1" and ev["type"] == "unseasonal_rain_post_harvest" and ev["status"] == "suspected"
    assert "78.4 mm" in ev["alert_message"]
    again = client.post("/api/monitor/run").json()
    assert again["new_events"] == [] and again["skipped"][0]["reason"] == "skipped_duplicate"


def test_monitor_dry(client, monkeypatch):
    _obs_patch(monkeypatch, {})
    assert client.post("/api/monitor/run").json()["new_events"] == []
    assert client.get("/api/events", params={"status": "suspected"}).json() == []


def test_event_state_machine(client, monkeypatch):
    _obs_patch(monkeypatch, {(26.926, "2026-10-28"): 78.4})
    eid = client.post("/api/monitor/run").json()["new_events"][0]["event_id"]
    assert client.post(f"/api/events/{eid}/evidence-pack").status_code == 409
    r = client.patch(f"/api/events/{eid}", json={"action": "confirm"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert r.json()["report_deadline"].startswith("2026-10-31T23:59")  # 28 Oct 23:59 IST + 72 h
    assert client.patch(f"/api/events/{eid}", json={"action": "confirm"}).status_code == 409


def test_post_harvest_type(client, monkeypatch):
    _obs_patch(monkeypatch, {(26.931, "2026-10-28"): 70.0})
    client.patch("/api/events/E1", json={"action": "dismiss"})  # E1 is confirmed: no-op 409, dedupe window is far
    ev = client.post("/api/monitor/run").json()["new_events"][0]
    assert ev["plot_id"] == "P2" and ev["type"] == "unseasonal_rain_post_harvest"


def test_simulation_is_labelled(client):
    r = client.post("/api/monitor/run", json={"simulate": {"plot_id": "P1", "date": "2026-10-29",
                                                           "precipitation_mm": 78.4}}).json()
    assert r["new_events"][0]["trigger_detail"].startswith("[SIMULATED FOR DEMO]")


# ---------- AC14-AC15 evidence pack ----------
def _pdf_text(client, url):
    pdf = client.get(url)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)


def test_pack_requires_confirmed(client, monkeypatch):
    _obs_patch(monkeypatch, {(26.926, "2026-10-28"): 78.4})
    eid = client.post("/api/monitor/run").json()["new_events"][0]["event_id"]
    r = client.post(f"/api/events/{eid}/evidence-pack")
    assert r.status_code == 409 and r.json()["detail"]["message"] == "Confirm the damage first to create an evidence pack."


def test_pack_contains_disclaimer_and_estimate(client):
    from tools.evidence_pack import DISCLAIMER, SECTION_TITLES
    r = client.post("/api/events/E1/evidence-pack")
    assert r.status_code == 200
    body = r.json()
    assert all(s["mode"] == "cached" for s in body["data_sources"])
    assert body["estimated_value"] == 18400.00
    text = re.sub(r"\s+", " ", _pdf_text(client, body["file_url"]))
    for title in SECTION_TITLES:
        assert title in text, title
    assert "DEMO SCENARIO ONLY" in text
    assert "not evidence of real crop damage" in text
    assert "Farmer's estimate" in text and "₹18,400.00" in text
    assert re.sub(r"\s+", " ", DISCLAIMER) in text
    assert "78.4" in text  # fixture rainfall on the event day
    assert "0.73" in text and "0.49" in text  # cached NDVI before/after


def test_ndvi_null_when_cloudy():
    from tools.climate import ndvi_change
    imgs = [{"date": "2026-10-10", "ndvi": 0.7, "masked_pct": 80}, {"date": "2026-10-18", "ndvi": 0.5, "masked_pct": 95}]
    out = ndvi_change(imgs, date(2026, 10, 14), [])
    assert out["ndvi_before"] is None and out["ndvi_after"] is None and out["ndvi_change_pct"] is None
    assert any("No cloud-free" in n for n in out["notes"])


def test_pack_without_satellite_still_generates(client, monkeypatch):
    from services import satellite
    monkeypatch.setattr(satellite, "get_images", lambda *a, **k: {"images": [
        {"date": "2026-10-10", "ndvi": 0.7, "masked_pct": 90}], "mode": "cached", "fixture_kind": "test", "source": "t"})
    r = client.post("/api/events/E1/evidence-pack")
    assert r.status_code == 200
    assert "No clear satellite image" in _pdf_text(client, r.json()["file_url"])


# ---------- AC16-AC18, SC5 agent ----------
def test_agent_fertiliser_compare(client):
    r = client.post("/api/agent/ask", json={"question": "Is season vs pichhle season khad par kitna kharch hua?"}).json()
    assert "₹4,600" in r["answer"] and "₹4,400" in r["answer"] and "4.5%" in r["answer"]
    assert r["mode"] == "fallback" and any(s["type"] == "ledger" for s in r["sources"])


def test_agent_refuses_dosage(client):
    r = client.post("/api/agent/ask", json={"question": "Tamatar par kitni dawa daalun?"}).json()
    assert "agriculture office" in r["answer"] and not re.search(r"\d", r["answer"])
    assert r["mode"] == "safety"


def test_agent_discloses_basic_mode_without_gemini_key(client):
    r = client.post("/api/agent/ask", json={"question": "Tell me about my farm"}).json()
    assert r["mode"] == "fallback"
    assert "Gemini is not configured" in r["notice"]


def test_agent_missing_record(client):
    r = client.post("/api/agent/ask", json={"question": "how much did I spend on tractor repair?"}).json()
    assert "I don't have a record of that in your ledger." in r["answer"]


def test_agent_never_sends(client):
    r = client.post("/api/agent/ask", json={"question": "send my claim to the insurer"}).json()
    assert "only prepare the record" in r["answer"] and r["tool_calls"] == []


def test_agent_claim_needs_confirmation(client):
    r = client.post("/api/agent/ask", json={"question": "prepare my claim file"}).json()
    assert r["pending_action"] == {"type": "generate_evidence_pack", "event_id": "E1"}
    assert client.get("/api/events/E1").json()["packs"] == []  # nothing generated until the user taps


def test_agent_tool_cap(monkeypatch, conn):
    from ai import agent, llm
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_messages(system, msgs, tools=None, max_tokens=0):
        calls["n"] += 1
        if tools is None:
            return {"content": [{"type": "text", "text": "Partial answer."}]}
        return {"content": [{"type": "tool_use", "id": f"t{calls['n']}", "name": "get_season_metrics",
                             "input": {"season_id": "S2"}}]}
    monkeypatch.setattr(llm, "messages", fake_messages)
    out = agent.ask(conn, "Tell me everything about plot 2")
    assert out["stopped_at_cap"] is True and len(out["tool_calls"]) == 6
    assert "I stopped early" in out["answer"]


def test_agent_spray_and_profit(client):
    r = client.post("/api/agent/ask", json={"question": "Can I spray tomorrow on plot 1?"}).json()
    assert r["spray"]["verdict"] == "not_advised"
    r = client.post("/api/agent/ask", json={"question": "Profit at today's price on plot 2?"}).json()
    assert "₹66,400" in r["answer"]


# ---------- AC19-AC21 ----------
def test_duplicate_entry(client):
    body = {"plot_id": "P1", "entry_date": "2026-10-30", "category": "labour", "item": "weeding", "cost_inr": 600}
    first = client.post("/api/entries", json=body)
    dup = client.post("/api/entries", json=body)
    assert dup.status_code == 409 and dup.json()["detail"]["entry_id"] == first.json()["entry_id"]
    assert client.post("/api/entries", json={**body, "force": True}).status_code == 201


def test_photo_too_big(client):
    big = b"\xff\xd8" + b"0" * (9 * 1024 * 1024)
    r = client.post("/api/photos", files={"file": ("big.jpg", big, "image/jpeg")}, data={"plot_id": "P1"})
    assert r.status_code == 413 and r.json()["detail"]["message"] == "Please use a photo smaller than 8 MB."


def test_photo_upload_and_type(client):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (0, 128, 0)).save(buf, "JPEG")
    r = client.post("/api/photos", files={"file": ("f.jpg", buf.getvalue(), "image/jpeg")}, data={"event_id": "E1"})
    assert r.status_code == 201 and r.json()["location_source"] == "plot_pin"
    bad = client.post("/api/photos", files={"file": ("f.gif", b"GIF89a", "image/gif")}, data={"plot_id": "P1"})
    assert bad.status_code == 415


def test_no_outbound_messaging_code():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    banned = re.compile(r"smtplib|sendgrid|twilio|whatsapp\.com|httpx\.post\((?!f\"\{settings\.llm_base_url)")
    for f in root.rglob("*.py"):
        if "tests" in f.parts or ".venv" in f.parts:
            continue
        assert not banned.search(f.read_text(encoding="utf-8")), f


def test_not_found(client):
    r = client.get("/api/events/E999")
    assert r.status_code == 404 and r.json()["detail"]["message"].startswith("We couldn't find")
