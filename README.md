# CropTrail

A farm memory with a brain. Farmers log their season in seconds (text, voice, photo), ask questions answered from their own records, get weather-risk advice per plot, and when severe weather hits, get a claim-ready evidence pack PDF in one tap.

Built from `specs.md` for the Climate, Resource Infrastructure & Global Supply Resilience track.

```
frontend/   Next.js 14 + Tailwind, mobile-first (Home, Log, Ledger, Ask, Alerts, Plots)
backend/    FastAPI + SQLite
  api/        route handlers
  models/     SQLite schema and helpers
  tools/      deterministic logic: metrics, spray check, risk, monitor, NDVI, evidence pack
  services/   Open-Meteo, Earth Engine, data.gov.in clients, each with cache + fixture fallback
  ai/         the ONLY module that calls the LLM (parser, agent, vision) + deterministic fallbacks
  config/     thresholds, crop calendar, keyword maps, claim fields
  seed/       demo seed, fixtures, fixture capture script
  tests/      acceptance tests (spec section 10)
```

## Run it (two terminals)

Prerequisites: Python 3.11+, Node 18+.

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env            # edit keys if you have them; all optional
uvicorn main:app --reload --port 8000

# 2. Frontend
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

The frontend proxies `/api/*` to `BACKEND_URL` (default `http://localhost:8000`), so you can open the app from a phone on the same Wi-Fi at `http://<laptop-ip>:3000`. Voice input needs Chrome and a secure context (localhost, or HTTPS when deployed).

The database seeds itself on first start. Reset any time from **Plots & seasons > Reset to demo data** or `POST /api/demo/reset`.

## Tests

```bash
cd backend && python -m pytest -q        # 37 tests covering AC1-AC22 and the named unit tests
cd frontend && npm run build             # production build must succeed
```

Tests run in fallback mode with `USE_CACHED_DATA=true` and a fixed clock of 2026-10-30 10:00 IST.

## Modes: what works without keys

| Integration | Without key / offline | With key |
|---|---|---|
| LLM (`LLM_API_KEY`) | Regex log parser + keyword agent covering 6 question types. "Demo mode" pill in header | Anthropic Messages API: JSON log parsing, tool-calling agent (max 6 tool calls), photo hints |
| Weather (Open-Meteo, no key) | `USE_CACHED_DATA=true` uses fixtures; on outage, last saved response < 24 h, else a clear error | Live forecast, observed history, 1991-2020 normals |
| Satellite (`GEE_SERVICE_ACCOUNT_JSON`) | Fixture NDVI for seeded plots P1/P2; other plots show "not available" | Live Sentinel-2 L2A NDVI with cloud masking (`pip install earthengine-api`) |
| Mandi (`DATA_GOV_IN_API_KEY` + `MANDI_RESOURCE_ID`) | `seed/fixtures/mandi.csv` (sample placeholder) | Agmarknet via data.gov.in |

Every number shown carries its source and a `live` / `cached` mode; synthetic fixtures are labelled "sample data" in the UI and in red in the PDF.

## Before the demo (important)

1. **Replace synthetic fixtures with real data.** The shipped weather/NDVI fixtures are synthetic so the app runs offline. With internet:
   ```bash
   cd backend && python -m seed.capture_fixtures
   ```
   This captures real Open-Meteo data for the seeded plot and prints the heaviest rain days.
2. **Set `DEMO_EVENT_DATE`** in `.env` to one of those real heavy-rain days, then reset the demo data. Never fabricate weather values.
3. **Replace the benchmark placeholder** in `seed/fixtures/benchmarks.csv` with the DES Cost of Cultivation values from data.gov.in.
4. **Verify claim rules** (72-hour window, required fields in `config/rules.py: CLAIM_FIELDS`) against the official PMFBY guidelines.
5. **Rehearse offline:** `USE_CACHED_DATA=true` makes every step work without a network.

### Showing the auto-trigger live

Real heavy rain rarely arrives on cue. With `ALLOW_SIMULATION=true`, **Alerts > Demo operator > Simulate rain and check** injects a rainfall value and runs the monitor. Everything it creates is marked `[SIMULATED FOR DEMO]` in the alert, the event, the chart (hatched bar) and the PDF. Set `ALLOW_SIMULATION=false` for anything that isn't a rehearsal.

## Suggested 2-minute demo

1. **Log:** type or say "kal plot 1 par 4 ghante paani diya ₹800" → Parse → Confirm.
2. **Ledger:** Nahar wala khet → cost per quintal ₹640, cost by category, NDVI curve dropping after the event.
3. **Ask:** "Fertiliser this season vs last?" (₹4,600 vs ₹4,400, +4.5%, with source chips) and "Can I spray tomorrow?" (rain-aware verdict).
4. **Alerts:** Simulate rain → amber alert on Home → Yes, damaged → add photo → Create evidence pack → PDF.

## Safety rails (in code, both modes)

- Never sends, files or submits anything; there is no outbound messaging code (checked by a test).
- Refuses pesticide/fertiliser doses, disease diagnosis and claim eligibility.
- The LLM never does arithmetic: all numbers come from SQL and deterministic tools; the agent only calls an allowlist with schema-validated arguments.
- Evidence packs require a confirmed event and a user tap; loss estimates are labelled as the farmer's own.
- EXIF is stripped from stored photos after reading time and GPS; no Aadhaar or bank details are collected.

## Known limitations

- No authentication: single-farmer demo. Anyone who can reach the server can read and change data.
- HEIC photos are stored but their EXIF time/GPS is not read (plot pin is used).
- Hindi UI strings cover the main flows; some backend-generated text (spray reasons, PDF) is English.
- Weather evidence is gridded model data (several km), not plot-level measurement; hail is rarely visible in it.
- NASA FIRMS fire alerts (N1), WhatsApp card (N2), a second regional language (N3) and offline sync (N4) are not built.
- The LLM path targets the Anthropic Messages API; switching provider means editing `backend/ai/llm.py` only.

## Troubleshooting

- **"Can't connect to CropTrail"** in the app: the backend isn't running on `BACKEND_URL`.
- **Weather unavailable (503):** no network and no cached forecast. Set `USE_CACHED_DATA=true`.
- **Voice button disabled:** the browser has no Web Speech API (use Chrome) or the page isn't on localhost/HTTPS.
- **Pinned clock for rehearsals:** set `CROPTRAIL_NOW=2026-10-30T10:00:00+05:30` in `.env`.
