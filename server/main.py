"""CropTrail API entrypoint. Run from this folder: uvicorn main:app --reload --port 8000"""
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router
from config.settings import settings
from models import db
from seed import seed
from tools import events

log = logging.getLogger("croptrail")


@asynccontextmanager
async def lifespan(_app):
    seed.ensure_seeded()
    if not settings.disable_scheduler:
        threading.Thread(target=_monitor_loop, daemon=True, name="weather-monitor").start()
    yield


app = FastAPI(title="CropTrail API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    fields = {}
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path")]
        fields[".".join(loc) or "request"] = e.get("msg", "invalid")
    return JSONResponse(status_code=422, content={"detail": {"message": "Please check the highlighted fields.",
                                                             "fields": fields}})


def _monitor_loop():
    while True:
        time.sleep(settings.monitor_interval_hours * 3600)
        try:
            with db.db() as conn:
                out = events.run_monitor(conn)
            log.info("weather monitor: %d plots, %d new events", out["checked_plots"], len(out["new_events"]))
        except Exception:  # never crash the server over a background check
            log.exception("weather monitor failed")


