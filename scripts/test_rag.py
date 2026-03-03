"""Quick RAG pipeline test — no robot required.

Runs ContentSyncWorker against the real GitHub content repo,
then fires a few test queries to verify retrieval is working.

Usage:
    cd reachy_mini_event_assistant_app
    uv run python scripts/test_rag.py
"""

from reachy_mini_event_assistant_app.config import config
from reachy_mini_event_assistant_app.rag.embeddings import Embeddings
from reachy_mini_event_assistant_app.rag.store import VectorStore
from reachy_mini_event_assistant_app.rag.sync import ContentSyncWorker

QUERIES = [
    ("What is the event about?", None),
    ("Who is speaking at the March event?", "events"),
    ("Where are the restrooms?", "venue"),
    ("How do I get there by train?", "venue"),
    ("Who are the sponsors?", "sponsors"),
    ("What is Agentic Engineering Chicago?", "about"),
]


def main() -> None:
    print(f"\nContent repo: {config.CONTENT_REPO_URL}")
    print(f"Qdrant path:  {config.QDRANT_PATH}")
    print(f"State file:   {config.INGEST_STATE_PATH}\n")

    store = VectorStore(path=config.QDRANT_PATH)
    embeddings = Embeddings(api_key=config.OPENAI_API_KEY or "")

    # Run sync (blocks until complete)
    print("--- Running content sync ---")
    worker = ContentSyncWorker(
        repo_url=config.CONTENT_REPO_URL,
        store=store,
        embeddings=embeddings,
        state_path=config.INGEST_STATE_PATH,
        branch=config.CONTENT_REPO_BRANCH,
    )
    worker.start()
    worker.join()

    if worker.error:
        print(f"\n❌ Sync failed: {worker.error}")
        return

    print("✓ Sync complete\n")

    # Fire test queries
    print("--- Test queries ---")
    for query, category in QUERIES:
        tag = f"[{category}]" if category else "[all]"
        vec = embeddings.embed_one(query)
        results = store.search(vec, category=category, limit=2)
        print(f"\nQ {tag}: {query}")
        if results:
            for r in results:
                snippet = r["text"][:120].replace("\n", " ")
                print(f"  ✓ [{r['source']}] (score={r['score']:.3f}) {snippet}...")
        else:
            print("  ✗ No results")

    print("\n--- Done ---\n")


if __name__ == "__main__":
    main()
