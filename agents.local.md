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
- App published at: https://huggingface.co/spaces/ksolo/reachy_mini_event_assistant_app

## Current State (last updated 2026-03-01)
All core modules built. See plan.md for full architecture.

**Next task — wire everything into main.py:**
- Instantiate VectorStore, Embeddings, LumaProvider at boot
- Start ContentSyncWorker background thread (block if first run / collection empty)
- Inject vector_store, embeddings, event_provider into ToolDependencies
- Wire PersonDetector to trigger greeting state

**Known issues / notes:**
- qdrant-client pinned to 1.12.1 (1.17.0 has grpc EnumTypeWrapper bug on Python 3.11)
- pyzbar gracefully disabled on macOS (libzbar path issue); works fine on Pi
- On macOS, set `DYLD_LIBRARY_PATH=/opt/homebrew/lib` if QR scanning needed locally

## Still Needed Before a Real Test Run
- Content GitHub repo: create it, set CONTENT_REPO_URL in .env
- Luma internal endpoint: capture via browser devtools Network tab while scanning QR
- .env file: copy .env.example → .env, fill in OPENAI_API_KEY, LUMA_AUTH_TOKEN, EVENT_NAME

## Key Notes
- SDK docs: `~/reachy_mini_resources/reachy_mini/docs/source/`
- SDK examples: `~/reachy_mini_resources/reachy_mini/examples/`
- REST API docs (when daemon running): `http://reachy-mini.local:8000/docs`
- Pi setup script: `scripts/setup_raspberry_pi.sh` (installs libzbar0 + uv)
