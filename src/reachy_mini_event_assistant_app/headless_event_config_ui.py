"""Settings UI routes for headless event configuration.

Exposes REST endpoints on the provided FastAPI settings app so that
operators can configure event-specific variables (CONTENT_REPO_URL,
EVENT_PROVIDER, EVENT_NAME, LUMA_SESSION_KEY, LUMA_CLIENT_VERSION)
via the browser without SSH access.

Mount with a single call alongside mount_personality_routes():

    from reachy_mini_event_assistant_app.headless_event_config_ui import mount_event_config_routes
    mount_event_config_routes(app, instance_path=self._instance_path)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_EVENT_CONFIG_KEYS = {
    "CONTENT_REPO_URL",
    "EVENT_PROVIDER",
    "EVENT_NAME",
    "LUMA_SESSION_KEY",
    "LUMA_CLIENT_VERSION",
}


def _read_env_lines(instance_path: str) -> list[str]:
    """Return lines from <instance_path>/.env, or [] if missing/unreadable."""
    env_path = Path(instance_path) / ".env"
    try:
        if env_path.exists():
            return env_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        pass
    return []


def _write_env_value(instance_path: str, key: str, value: str) -> None:
    """Set or append KEY=value in <instance_path>/.env and reload into process env."""
    env_path = Path(instance_path) / ".env"
    lines = _read_env_lines(instance_path)
    replaced = False
    prefix = f"{key}="
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    try:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to write %s to .env: %s", key, e)
        return

    # Reload into process env so config and os.getenv callers see it immediately
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=str(env_path), override=True)
    except Exception:
        pass


def _update_config(key: str, value: str) -> None:
    """Update the live config object for a given env key."""
    try:
        from reachy_mini_event_assistant_app.config import config
        setattr(config, key, value)
    except Exception:
        pass
    try:
        os.environ[key] = value
    except Exception:
        pass


def mount_event_config_routes(
    app: object,
    *,
    instance_path: Optional[str],
) -> None:
    """Register event config endpoints on a FastAPI app.

    Endpoints added:
        GET  /event_config  — returns current values (LUMA_SESSION_KEY masked)
        POST /event_config  — saves any subset of the 5 event config keys
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel
        if not isinstance(app, FastAPI):
            return
    except Exception:
        return

    class EventConfigPayload(BaseModel):
        content_repo_url: Optional[str] = None
        event_provider: Optional[str] = None
        event_name: Optional[str] = None
        luma_session_key: Optional[str] = None
        luma_client_version: Optional[str] = None

    @app.get("/event_config")
    def _get_event_config() -> JSONResponse:
        try:
            from reachy_mini_event_assistant_app.config import config
            return JSONResponse({
                "content_repo_url": config.CONTENT_REPO_URL or "",
                "event_provider": config.EVENT_PROVIDER or "luma",
                "event_name": config.EVENT_NAME or "",
                "has_luma_session_key": bool(config.LUMA_SESSION_KEY and str(config.LUMA_SESSION_KEY).strip()),
                "luma_client_version": config.LUMA_CLIENT_VERSION or "",
            })
        except Exception as e:
            logger.warning("GET /event_config error: %s", e)
            return JSONResponse({"error": "config_unavailable"}, status_code=500)

    @app.post("/event_config")
    def _post_event_config(payload: EventConfigPayload) -> JSONResponse:
        mapping = {
            "CONTENT_REPO_URL": payload.content_repo_url,
            "EVENT_PROVIDER": payload.event_provider,
            "EVENT_NAME": payload.event_name,
            "LUMA_SESSION_KEY": payload.luma_session_key,
            "LUMA_CLIENT_VERSION": payload.luma_client_version,
        }
        updated = []
        for env_key, value in mapping.items():
            if value is None:
                # Not included in payload — leave existing value alone
                continue
            v = value.strip()
            if env_key == "LUMA_SESSION_KEY" and not v:
                # Empty password field means "keep existing" — skip
                continue
            _update_config(env_key, v)
            if instance_path:
                _write_env_value(instance_path, env_key, v)
            updated.append(env_key)

        logger.info("Event config updated: %s", updated)
        return JSONResponse({"ok": True, "updated": updated})
