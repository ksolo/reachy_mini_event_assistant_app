import logging

from openai import OpenAI


logger = logging.getLogger(__name__)

MODEL = "text-embedding-3-small"


class Embeddings:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=MODEL, input=texts)
        return [item.embedding for item in response.data]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
