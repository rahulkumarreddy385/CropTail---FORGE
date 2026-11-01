# CropTrail

A farm memory with a brain. Farmers log their season in seconds (text, voice, photo), ask questions answered from their own records, get weather-risk advice per plot, and when severe weather hits, get a claim-ready evidence pack PDF in one tap.

Built from `specs.md` for the Climate, Resource Infrastructure & Global Supply Resilience track.

```
client/     Next.js 14 + Tailwind, mobile-first (Home, Log, Ledger, Ask, Alerts, Plots)
server/     FastAPI + SQLite
  api/        route handlers
  models/     SQLite schema and helpers
  tools/      deterministic logic: metrics, spray check, risk, monitor, NDVI, evidence pack
  services/   Open-Meteo, Earth Engine, data.gov.in clients, with saved-real-data cache
  ai/         the ONLY module that calls the LLM (parser, agent, vision) + deterministic fallbacks
  config/     thresholds, crop calendar, keyword maps, claim fields
  seed/       demo seed, fixtures, fixture capture script
  tests/      acceptance tests (spec section 10)
```

## Run it (two terminals)

Prerequisites: Python 3.11+, Node 18+.

```powershell
# 1. Server (terminal 1)
Set-Location server
python -m pip install -r requirements.txt
# Create or edit .env without replacing any existing API keys:
# GEMINI_API_KEY=your-gemini-api-key
# LLM_MODEL=gemini-3.8-flash
# USE_CACHED_DATA=false
# ALLOW_SAMPLE_FIXTURES=false
# DATA_GOV_IN_API_KEY=your-data-gov-in-key
# MANDI_RESOURCE_ID=your-agmarknet-resource-id
# GEE_SERVICE_ACCOUNT_JSON=./secrets/your-service-account.json
uvicorn main:app --reload --port 8000
```

```powershell
# 2. Client (terminal 2, from the project root)
Set-Location client
npm ci
npm run dev                     # http://localhost:3000
```

The client proxies `/api/*` to `SERVER_URL` (default `http://localhost:8000`), so you can open the app from a phone on the same Wi-Fi at `http://<laptop-ip>:3000`. Voice input needs Chrome and a secure context (localhost, or HTTPS when deployed).

The database seeds itself on first start. **Reset to demo data replaces the database contents**, so back up `server/croptrail.db` first if it contains records you need. The same destructive reset is available at `POST /api/demo/reset`.

## Free hosted demo (Render)

The repository includes a Render Blueprint in `render.yaml` for the client and server using Render's free web services. Free services can sleep when idle and have an ephemeral filesystem: SQLite records and uploaded photos can be lost when a service restarts or redeploys. The demo seed is restored when the server starts with an empty database. Do not enter real or sensitive farm records in this free deployment.

1. Push this repository to GitHub without API keys or the `server/secrets/` directory. `server/.env` and `server/secrets/` are ignored by Git; do not put secrets in the tracked `client/.env` file.
2. In Render, create a Blueprint from this repository and confirm both services use the free plan.
3. Set the prompted `APP_PASSWORD` to a unique password with at least 16 characters. Render generates `SESSION_SECRET`; keep it private.
4. Add `GEMINI_API_KEY`, `DATA_GOV_IN_API_KEY` and `MANDI_RESOURCE_ID` in the Render dashboard if needed. Local `.env` values are not copied automatically. Earth Engine credentials must be uploaded as a Render secret file and `GEE_SERVICE_ACCOUNT_JSON` set to that file's path.
5. After deploy, open the client URL and sign in. The demo dataset is automatically seeded on the first empty database. It is fictional; do not treat its alerts or evidence PDF as real.

Hosted mode enforces password auth at the API, uses secure HTTP-only session cookies, and disables sample fixtures and the background monitor by default. This is a protected, disposable single-user demo, not production-grade multi-user farm software. Keep the password private and do not enter sensitive personal/farm records.

## Tests

```powershell
# In PowerShell, from the repository root:
Set-Location server
$env:PYTHONUTF8 = "1"
python -m pytest -q

Set-Location ..\client
npm run build
```

Tests run with explicit sample fixtures enabled, cached-data mode, and a fixed clock of 2026-10-30 10:00 IST.

## Modes: what works without keys

| Integration | Without key / offline | With key |
|---|---|---|
| LLM (`GEMINI_API_KEY`) | Regex log parser + keyword agent covering 6 question types. Basic-answer label | Gemini API (`gemini-3.8-flash` by default): JSON log parsing, function-calling agent (max 6 tool calls), photo hints |
| Weather (Open-Meteo, no key) | Last saved real response, otherwise clearly unavailable | Live forecast, observed history, 1991-2020 normals |
| Satellite (`GEE_SERVICE_ACCOUNT_JSON`) | Last saved real response, otherwise "not available" | Live Sentinel-2 L2A NDVI with cloud masking |
| Mandi (`DATA_GOV_IN_API_KEY` + `MANDI_RESOURCE_ID`) | Last saved real price, otherwise unavailable | Agmarknet via data.gov.in |

Weather, satellite and mandi data use live sources or previously saved real responses. Sample fixtures are disabled by default (`ALLOW_SAMPLE_FIXTURES=false`) and only activate when both `USE_CACHED_DATA=true` and `ALLOW_SAMPLE_FIXTURES=true`. The health response reports whether sample fixtures are enabled; the home screen warns when demo farm records are loaded. The demo farmer, plots, ledger entries, tomato sales, loss scenario and placeholder photos are entirely fictional; the sample mandi prices are examples, not current quotes.

The seed contains a paddy season comparison (2025 vs 2026) with harvest, partial sale and an illustrative weather-loss scenario, plus a tomato season with multiple input/labour records, two pickings and partial sales. This makes ledger totals, cost per quintal, revenue, profit, Q&A and evidence-pack flows demonstrable without presenting the records as real. The demo evidence PDF is prominently marked fictional and must not be used for a claim.

## Before the demo (important)

1. **Use real external data.** Open-Meteo needs no key. For satellite data, configure an Earth Engine service-account JSON file and set `GEE_SERVICE_ACCOUNT_JSON` to its path. For mandi prices, configure both `DATA_GOV_IN_API_KEY` and the Agmarknet `MANDI_RESOURCE_ID`; the API key alone is not enough. Keep these values in `server/.env`, not in chat or source control. The local health endpoint initially says `configured` until a request verifies the integration; after use it reports the last mode (`live`, `cached`, or `unavailable`).
2. **Optional offline demo only:** set both `ALLOW_SAMPLE_FIXTURES=true` and `USE_CACHED_DATA=true`. The UI will clearly warn that sample data may be synthetic. To capture weather for that offline demo:
   ```bash
   Set-Location server
   python -m seed.capture_fixtures
   ```
3. **Benchmarks:** the bundled cost-of-cultivation CSV is sample data and is not shown in real-data mode; no live benchmark API is configured.
4. **Verify claim rules** (72-hour window, required fields in `config/rules.py: CLAIM_FIELDS`) against the official PMFBY guidelines.

### Showing the auto-trigger live

Real heavy rain rarely arrives on cue. With `ALLOW_SIMULATION=true`, **Alerts > Demo operator > Simulate rain and check** injects a rainfall value and runs the monitor. Everything it creates is marked `[SIMULATED FOR DEMO]` in the alert, the event, the chart (hatched bar) and the PDF. Set `ALLOW_SIMULATION=false` for anything that isn't a rehearsal.

## Suggested 2-minute demo

1. **Log:** type or say "kal plot 1 par 4 ghante paani diya ₹800" → Parse → Confirm.
2. **Ledger:** compare the two paddy seasons (₹500 vs ₹640 per quintal), or view the tomato plot’s 11 q harvest and partial sales. These are sample figures.
3. **Ask:** "Fertiliser this season vs last?" (₹4,600 vs ₹4,400, +4.5%, with source chips) and "Can I spray tomorrow?" (rain-aware verdict).
4. **Alerts:** Simulate rain → amber alert on Home → Yes, damaged → add photo → Create evidence pack → PDF.

## Safety rails (in code, both modes)

- Never sends, files or submits anything; there is no outbound messaging code (checked by a test).
- Refuses pesticide/fertiliser doses, disease diagnosis and claim eligibility.
- The LLM never does arithmetic: all numbers come from SQL and deterministic tools; the agent only calls an allowlist with schema-validated arguments.
- Evidence packs require a confirmed event and a user tap; loss estimates are labelled as the farmer's own. Seeded demo events and PDFs are additionally labelled fictional and must not be submitted.
- EXIF is stripped from stored photos after reading time and GPS; no Aadhaar or bank details are collected.

## Known limitations

- No authentication: single-farmer demo. Anyone who can reach the server can read and change data.
- HEIC photos are stored but their EXIF time/GPS is not read (plot pin is used).
- Hindi UI strings cover the main flows; some server-generated text (spray reasons, PDF) is English.
- Weather evidence is gridded model data (several km), not plot-level measurement; hail is rarely visible in it.
- NASA FIRMS fire alerts (N1, intentionally skipped for now), WhatsApp card (N2), a second regional language (N3) and offline sync (N4) are not built.
- The LLM integration uses the Gemini `generateContent` API through `server/ai/llm.py`.
- Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey), then put it in `server/.env` as `GEMINI_API_KEY=...`. Never paste it into chat or commit it. The app uses `gemini-3.8-flash`.

## Troubleshooting

- **"Can't connect to CropTrail"** in the app: the server isn't running at `SERVER_URL`.
- **Weather unavailable (503):** no network and no saved real forecast. Reconnect to fetch live data.
- **Mandi price unavailable:** verify both `DATA_GOV_IN_API_KEY` and the exact Agmarknet `MANDI_RESOURCE_ID`; restart the server after changing `.env`.
- **Satellite data unavailable:** verify `GEE_SERVICE_ACCOUNT_JSON` points to a readable Earth Engine service-account file and that the account/project has Earth Engine access.
- **Gemini unavailable (HTTP 503):** Google returned a temporary service error; it does not by itself mean the API key is invalid. Retry later and check the model/API status page.
- **Voice button disabled:** the browser has no Web Speech API (use Chrome) or the page isn't on localhost/HTTPS.
- **Pinned clock for rehearsals:** set `CROPTRAIL_NOW=2026-10-30T10:00:00+05:30` in `.env`.
