# agents.local.md — Reachy Mini Event Assistant App

## Setup Status
- Environment setup: complete
- Setup date: 2026-03-01

## User Preferences
- Python tool: uv (each project has its own .venv)
- Shell: fish
- Python version: 3.11.12 (via asdf — use `python`, not `python3`)
- Use `uv add <package>` to add dependencies, never edit pyproject.toml manually

## Robot Configuration
- Hardware: Wireless (onboard CM4)
- Development mode: Simulator (robot is at the office)
- Target deployment: Wireless robot over WiFi (`reachy-mini.local:8000`)

## Paths
- Resources directory: `~/reachy_mini_resources/`
  - SDK clone: `~/reachy_mini_resources/reachy_mini/`
  - Resources venv (SDK only): `~/reachy_mini_resources/.venv/`
- Projects directory: `~/Projects/reachy/`
  - This app: `reachy_mini_event_assistant_app/` (has its own .venv)
  - Reference app: `reachy_mini_conversation_app/`
- Content repo: `~/Projects/reachy/agentic-engineering-chicago/`
- App published at: https://huggingface.co/spaces/ksolo/reachy_mini_event_assistant_app

## Current State (last updated 2026-03-03)
All core modules built and verified. App is feature-complete for the March 24 event.

**All wiring complete:**
- VectorStore, Embeddings, ContentSyncWorker, LumaProvider all boot correctly
- PersonDetector wired into main.py and greeting signal wired into OpenaiRealtimeHandler
- RAG sync tested clean (template.md excluded, all 6 test queries pass)
- Luma check-in API tested and verified against live event (200 response, guest name extracted)
- data/ added to .gitignore (runtime-generated, recreated automatically on boot)

**Tunable constants (adjust after testing on physical robot):**
- `camera/person_detect.py`: `MOTION_AREA_THRESHOLD = 3000` (px on 320×240 frame)
- `camera/person_detect.py`: `DETECTION_COOLDOWN_S = 30.0` (seconds)
- `camera/person_detect.py`: `QUIET_FRAMES_TO_RESET = 30` (~3s of no motion resets cooldown)

## Before the Real Event
- SSH into robot, clone repo, run `uv sync`, copy `.env.example` → `.env`
- Fill in `OPENAI_API_KEY` and `LUMA_SESSION_KEY` (capture fresh from browser devtools day-of)
- If Luma deploys between now and event day, recapture `LUMA_CLIENT_VERSION` from devtools
- QR scanning uses OpenCV's built-in detector — no extra system libraries needed

## Known Issues / Notes
- qdrant-client pinned to 1.12.1 (1.17.0 has grpc EnumTypeWrapper bug on Python 3.11)
- MuJoCo simulator on macOS requires `libpython3.11.dylib` — needs asdf Python rebuilt
  with `PYTHON_CONFIGURE_OPTS="--enable-shared"`. Skip simulator testing on macOS for now.
- LUMA_SESSION_KEY will expire — recapture from browser devtools close to event day
- LUMA_CLIENT_VERSION is a Luma frontend git hash — update in .env if check-in breaks

## Luma Check-in Details
- Endpoint: `POST https://api2.luma.com/event/admin/update-check-in`
- Auth: cookie `luma.auth-session-key` (stored as LUMA_SESSION_KEY in .env)
- QR format: `https://luma.com/check-in/{event_api_id}?pk={rsvp_api_id}`
- Response: `data["guest"]["first_name"]` for greeting name
- Undocumented internal API — fragile by nature

## Key Notes
- SDK docs: `~/reachy_mini_resources/reachy_mini/docs/source/`
- SDK examples: `~/reachy_mini_resources/reachy_mini/examples/`
- REST API docs (when daemon running): `http://reachy-mini.local:8000/docs`
- RAG test script: `scripts/test_rag.py` (run after content changes to verify retrieval)
