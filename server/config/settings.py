"""Runtime settings, read from environment variables (see server/.env)."""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SERVER_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader so the app runs with one command. Real env vars win."""
    env_file = SERVER_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            value = value.split("#", 1)[0].rstrip()
        os.environ.setdefault(key.strip(), value)


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    value = _env(name, "true" if default else "false").lower()
    return value in ("1", "true", "yes", "on")


class Settings:
    """Re-read on every access so tests can change env vars at runtime."""

    @property
    def llm_api_key(self) -> str:
        return _env("GEMINI_API_KEY") or _env("LLM_API_KEY")

    @property
    def llm_model(self) -> str:
        return _env("LLM_MODEL", "gemini-3.8-flash")

    @property
    def llm_base_url(self) -> str:
        return _env("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    @property
    def data_gov_in_api_key(self) -> str:
        return _env("DATA_GOV_IN_API_KEY")

    @property
    def mandi_resource_id(self) -> str:
        return _env("MANDI_RESOURCE_ID")

    @property
    def gee_service_account_json(self) -> str:
        return _env("GEE_SERVICE_ACCOUNT_JSON")

    @property
    def database_path(self) -> Path:
        p = Path(_env("DATABASE_PATH", "./croptrail.db"))
        return p if p.is_absolute() else SERVER_DIR / p

    @property
    def upload_dir(self) -> Path:
        p = Path(_env("UPLOAD_DIR", "./uploads"))
        p = p if p.is_absolute() else SERVER_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache_dir(self) -> Path:
        p = SERVER_DIR / ".cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def client_origin(self) -> str:
        return _env("CLIENT_ORIGIN", "http://localhost:3000")

    @property
    def monitor_interval_hours(self) -> float:
        return float(_env("MONITOR_INTERVAL_HOURS", "6"))

    @property
    def heavy_rain_mm(self) -> float:
        return float(_env("HEAVY_RAIN_MM", "64.5"))

    @property
    def report_window_hours(self) -> int:
        return int(_env("REPORT_WINDOW_HOURS", "72"))

    @property
    def spray_rain_lookahead_hours(self) -> int:
        return int(_env("SPRAY_RAIN_LOOKAHEAD_HOURS", "24"))

    @property
    def demo_event_date(self) -> str:
        return _env("DEMO_EVENT_DATE", "2026-10-14")

    @property
    def use_cached_data(self) -> bool:
        return _bool("USE_CACHED_DATA", False)

    @property
    def allow_sample_fixtures(self) -> bool:
        return _bool("ALLOW_SAMPLE_FIXTURES", False)

    @property
    def sample_data_enabled(self) -> bool:
        return self.use_cached_data and self.allow_sample_fixtures

    @property
    def allow_simulation(self) -> bool:
        return _bool("ALLOW_SIMULATION", False)

    @property
    def disable_scheduler(self) -> bool:
        return _bool("DISABLE_SCHEDULER", False)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(_env("TIMEZONE", "Asia/Kolkata"))

    def now(self) -> datetime:
        """Current time in the app timezone. CROPTRAIL_NOW pins the clock (tests, demo rehearsals)."""
        fixed = _env("CROPTRAIL_NOW")
        if fixed:
            dt = datetime.fromisoformat(fixed)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.timezone)
            return dt.astimezone(self.timezone)
        return datetime.now(self.timezone)

    def today(self):
        return self.now().date()


settings = Settings()
