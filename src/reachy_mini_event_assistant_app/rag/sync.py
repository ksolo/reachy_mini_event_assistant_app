"""ContentSyncWorker — runs once at boot in a background thread.

Flow:
  1. Fetch file tree + SHAs from GitHub
  2. Diff against data/ingest_state.json
  3. Re-embed only changed/new files; delete removed files
  4. Write updated ingest_state.json
  5. Signal ready (used to block first-run startup), then exit
"""

import hashlib
import json
import logging
import threading
from pathlib import Path

from qdrant_client.models import PointStruct

from reachy_mini_event_assistant_app.rag.embeddings import Embeddings
from reachy_mini_event_assistant_app.rag.loader import (
    build_chunks,
    get_file_tree,
    get_repo_sha,
    parse_owner_repo,
)
from reachy_mini_event_assistant_app.rag.store import VectorStore


logger = logging.getLogger(__name__)


def _point_id(source_file: str, chunk_index: int) -> str:
    """Stable deterministic ID for a chunk."""
    raw = f"{source_file}:{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


class ContentSyncWorker(threading.Thread):
    def __init__(
        self,
        repo_url: str,
        store: VectorStore,
        embeddings: Embeddings,
        state_path: str,
        branch: str = "main",
    ) -> None:
        super().__init__(name="ContentSyncWorker", daemon=True)
        self._repo_url = repo_url
        self._store = store
        self._embeddings = embeddings
        self._state_path = Path(state_path)
        self._branch = branch
        self.ready = threading.Event()
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            self._sync()
        except Exception as e:
            logger.error("ContentSyncWorker failed: %s", e, exc_info=True)
            self.error = e
        finally:
            # Always signal ready so the app doesn't hang on first-run wait
            self.ready.set()

    def _load_state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        return {"repo_sha": None, "files": {}}

    def _save_state(self, state: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, indent=2))

    def _sync(self) -> None:
        owner, repo = parse_owner_repo(self._repo_url)
        logger.info("ContentSyncWorker: checking %s/%s", owner, repo)

        current_tree = get_file_tree(owner, repo, self._branch)
        repo_sha = get_repo_sha(owner, repo, self._branch)
        state = self._load_state()
        stored_files: dict[str, str] = state.get("files", {})

        changed = [path for path, sha in current_tree.items() if stored_files.get(path) != sha]
        removed = [path for path in stored_files if path not in current_tree]

        if not changed and not removed:
            logger.info("ContentSyncWorker: content up to date, nothing to do")
            return

        logger.info("ContentSyncWorker: %d changed, %d removed files", len(changed), len(removed))

        # Delete chunks for removed or changed files
        for path in removed + changed:
            self._store.delete_by_file(path)

        # Embed and upsert changed files
        if changed:
            chunks = build_chunks(owner, repo, changed, self._branch)
            texts = [c.text for c in chunks]
            vectors = self._embeddings.embed(texts)

            points = [
                PointStruct(
                    id=_point_id(c.source_file, c.chunk_index),
                    vector=vec,
                    payload={
                        "text": c.text,
                        "source_file": c.source_file,
                        "category": c.category,
                    },
                )
                for c, vec in zip(chunks, vectors)
            ]
            self._store.upsert(points)
            logger.info("ContentSyncWorker: upserted %d chunks", len(points))

        # Update state
        new_files = {**stored_files, **{p: current_tree[p] for p in changed}}
        for path in removed:
            new_files.pop(path, None)
        self._save_state({"repo_sha": repo_sha, "files": new_files})
        logger.info("ContentSyncWorker: sync complete")
