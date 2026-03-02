# Plan: Reachy Mini Event Assistant App

## Understanding

An in-person event assistant robot that:
1. Watches for approaching guests (camera-based person detection)
2. Greets them with a warm welcome (emotion + speech)
3. Answers questions about the event via voice (RAG over a GitHub content repo)
4. Checks in guests by scanning their QR code (camera + event provider API)

**Target hardware:** Reachy Mini Wireless
**Development mode:** Simulator (camera features untestable in sim — antenna press triggers greeting)
**Template base:** `conversation` (OpenAI Realtime voice pipeline already wired)

---

## Technical Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Voice (STT + LLM + TTS) | OpenAI Realtime API | Already in scaffolded template |
| RAG / embeddings | OpenAI `text-embedding-3-small` | Same key, no extra vendor |
| Vector store | Qdrant Edge (embedded) | `qdrant-client` path-based, persists to disk |
| Content source | Public GitHub repo (markdown files) | Fetched at boot via GitHub API |
| Person detection | OpenCV (motion/face) | Lightweight for CM4; antenna trigger in sim |
| QR scanning | `pyzbar` + OpenCV | Decode from camera frame |
| Event check-in | Abstracted provider pattern | Luma stub now; Eventbrite etc. later |

---

## Architecture

### State Machine

```
IDLE ──(person detected)──→ GREETING ──→ INTERACTION ──(farewell)──→ IDLE
                                               │
                               ┌───────────────┼───────────────┐
                               ↓               ↓               ↓
                           QR SCAN            Q&A           (end)
                               │               │
                        EventProvider      Qdrant RAG
                        .checkin_guest()   + GPT-4o
```

### Boot Sequence

```
App starts
  │
  ├─ [background thread] ContentSyncWorker
  │    ├─ GET GitHub file tree + SHAs via API
  │    ├─ Diff against data/ingest_state.json
  │    ├─ For each changed/new file:
  │    │    ├─ Fetch raw markdown content
  │    │    ├─ Chunk by markdown section (## headers)
  │    │    ├─ Tag chunks with category (directory name) + source file metadata
  │    │    ├─ Embed with text-embedding-3-small
  │    │    └─ Upsert to Qdrant (deterministic IDs → safe to re-run)
  │    ├─ Write updated data/ingest_state.json
  │    └─ Signal "ready" if first run, then EXIT (no polling)
  │
  └─ [main thread] App startup
       ├─ If Qdrant collection empty (first run): WAIT for ContentSyncWorker "ready" signal
       └─ If collection exists: continue booting immediately, serve stale data while sync runs
```

### Content Repo Structure

The GitHub repo's `README.md` describes the directory layout. The pipeline
loads all `.md` files recursively and tags each chunk with its parent directory
as `category` metadata — enabling filtered retrieval.

```
event-content/          ← CONTENT_REPO_URL points here
├── README.md           ← human-readable description of structure
├── events/             ← category: "events" (updated a few times/month)
├── venue/              ← category: "venue" (rarely changes)
├── meetups/            ← category: "meetups"
└── sponsors/           ← category: "sponsors"
```

Chunk point ID: `hash(f"{file_path}:{chunk_index}:{file_sha}")` — deterministic,
safe to upsert, old chunks for a changed file are deleted before inserting new ones.

### New Files to Add

The scaffolded template already provides: `openai_realtime.py`, `moves.py`,
`camera_worker.py`, `tools/`, `audio/`, `vision/`. We add:

```
src/reachy_mini_event_assistant_app/
│
├── checkin/                         # Event provider abstraction
│   ├── __init__.py
│   ├── base.py                      # Abstract EventProvider + CheckinResult dataclass
│   ├── luma.py                      # Luma stub (reverse-engineered internal endpoint)
│   └── eventbrite.py                # Placeholder for future Eventbrite support
│
├── rag/                             # RAG pipeline
│   ├── __init__.py
│   ├── sync.py                      # ContentSyncWorker (background thread, runs once)
│   ├── loader.py                    # GitHub API fetch + markdown chunker
│   ├── embeddings.py                # OpenAI text-embedding-3-small wrapper
│   └── store.py                     # Qdrant Edge client (path-based)
│
├── tools/
│   ├── ... (existing tools kept)
│   ├── event_qa.py                  # answer_event_question(query) → RAG lookup
│   └── checkin.py                   # checkin_guest() → QR scan + EventProvider
│
├── camera/
│   ├── __init__.py
│   ├── person_detect.py             # OpenCV motion/face → person_detected event
│   └── qr_scanner.py                # pyzbar decode from camera frame
│
└── config.py                        # EXTEND — add RAG + provider config vars
```

---

## Key Design Decisions

### 1. Event Provider Abstraction

```python
# checkin/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CheckinResult:
    success: bool
    guest_name: str | None
    message: str           # spoken back to guest by the robot

class EventProvider(ABC):
    @abstractmethod
    def checkin_guest(self, qr_data: str) -> CheckinResult: ...

    @abstractmethod
    def get_event_name(self) -> str: ...
```

Provider selected via `EVENT_PROVIDER` env var. Swap without touching any other code.

### 2. Luma Stub

```python
# checkin/luma.py
# QR code URL format: https://luma.com/check-in/{event_id}?pk={key}
# Parses event_id and pk from URL, POSTs to internal Luma endpoint.
# Endpoint URL + required headers TBD — capture via browser devtools Network tab.
```

### 3. Qdrant Edge

```python
# rag/store.py
from qdrant_client import QdrantClient
client = QdrantClient(path="./data/qdrant")  # persists across reboots
```

### 4. Incremental Sync State

```json
// data/ingest_state.json
{
  "repo_sha": "abc123",
  "files": {
    "venue/details.md": "sha_xyz",
    "events/march-meetup.md": "sha_abc"
  }
}
```

Past event files: SHA never changes → never re-ingested after first time. ✓

### 5. LLM Tools (follow existing pattern)

```
Realtime API → tool call → tool fn → direct response (Q&A) or queue (robot motion)
```

New tools:
- `answer_event_question(query)` — filtered Qdrant search → GPT-4o answer
- `checkin_guest()` — camera QR scan → `EventProvider.checkin_guest()`

---

## Configuration

`.env` file — placed on the robot via SSH, persists across reboots:

```bash
# Existing
OPENAI_API_KEY=sk-...

# New
CONTENT_REPO_URL=https://github.com/you/your-event-content
EVENT_PROVIDER=luma
LUMA_AUTH_TOKEN=...          # captured from browser session (TBD)
QDRANT_PATH=./data/qdrant
INGEST_STATE_PATH=./data/ingest_state.json
```

Set via: `ssh reachy@reachy-mini.local`, then edit `.env` in the app directory.

---

## Implementation Order

1. **`rag/store.py`** — Qdrant Edge client wrapper
2. **`rag/embeddings.py`** — OpenAI embeddings wrapper
3. **`rag/loader.py`** — GitHub API fetch + markdown chunker
4. **`rag/sync.py`** — ContentSyncWorker (background thread, incremental, run-once)
5. **`checkin/base.py`** — Abstract EventProvider + CheckinResult
6. **`checkin/luma.py`** — Luma stub (QR URL parser + placeholder POST)
7. **`checkin/eventbrite.py`** — Placeholder class only
8. **`tools/event_qa.py`** — answer_event_question LLM tool
9. **`tools/checkin.py`** — checkin_guest LLM tool
10. **`camera/qr_scanner.py`** — pyzbar QR decoder (stubbed for simulator)
11. **`camera/person_detect.py`** — OpenCV person detection (antenna fallback for sim)
12. **`config.py`** — extend with new env vars + provider selection
13. **`profiles/.../instructions.txt`** — event-host persona + tool awareness
14. **End-to-end wiring** in `main.py` — boot sequence, sync worker, state machine

---

## Open Questions

1. **Luma internal endpoint** — Capture HTTP request from Luma web check-in UI
   (browser devtools → Network tab) to get exact URL, headers, and body format.
2. **Content repo URL** — What is the GitHub repo URL for event content?
3. **Event content for dev/testing** — Create placeholder markdown files to test
   RAG before the real content repo is ready.
