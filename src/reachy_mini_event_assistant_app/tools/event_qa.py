import logging
from typing import Any, Dict

from reachy_mini_event_assistant_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class EventQA(Tool):
    """Answer questions about the event using the RAG knowledge base."""

    name = "answer_event_question"
    description = (
        "Answer a question about the event, venue, schedule, speakers, sponsors, or meetup group. "
        "Use this whenever someone asks for information about the event."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The question to look up in the event knowledge base.",
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional category filter to narrow the search. "
                    "One of: events, venue, meetups, sponsors, general."
                ),
            },
        },
        "required": ["query"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        category = kwargs.get("category") or None

        if not query:
            return {"error": "query is required"}

        if deps.vector_store is None or deps.embeddings is None:
            return {"error": "RAG pipeline not available"}

        try:
            query_vector = deps.embeddings.embed_one(query)
            results = deps.vector_store.search(query_vector, category=category, limit=5)

            if not results:
                return {"answer": "I don't have specific information about that. Please ask an organizer."}

            context = "\n\n---\n\n".join(
                f"[{r['source']}]\n{r['text']}" for r in results
            )
            return {"context": context}

        except Exception as e:
            logger.error("event_qa failed: %s", e, exc_info=True)
            return {"error": f"Knowledge base lookup failed: {e}"}
