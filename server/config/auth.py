"""Signed single-user sessions for hosted deployments."""
import base64
import hashlib
import hmac
import secrets
import time

from config.settings import settings

SESSION_TTL_SECONDS = 12 * 60 * 60


def _signature(payload: str) -> str:
    digest = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_session() -> str:
    payload = f"{int(time.time()) + SESSION_TTL_SECONDS}.{secrets.token_urlsafe(24)}"
    return f"{payload}.{_signature(payload)}"


def valid_session(token: str | None) -> bool:
    if not settings.auth_enabled or not token:
        return not settings.auth_enabled
    try:
        expires, nonce, signature = token.split(".", 2)
        payload = f"{expires}.{nonce}"
        return int(expires) > int(time.time()) and hmac.compare_digest(signature, _signature(payload))
    except (ValueError, TypeError):
        return False


def valid_password(password: str) -> bool:
    return settings.auth_enabled and hmac.compare_digest(password, settings.app_password)
