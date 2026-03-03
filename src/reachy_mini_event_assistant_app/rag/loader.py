import logging
import re
from dataclasses import dataclass

import requests


logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
CHUNK_MIN_CHARS = 100


@dataclass
class Chunk:
    text: str
    source_file: str
    category: str
    chunk_index: int


def parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    # handles https://github.com/owner/repo or https://github.com/owner/repo.git
    parts = repo_url.rstrip("/").rstrip(".git").split("/")
    return parts[-2], parts[-1]


def get_file_tree(owner: str, repo: str, branch: str = "main") -> dict[str, str]:
    """Return {file_path: sha} for all .md files in the repo."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return {
        item["path"]: item["sha"]
        for item in tree
        if item["type"] == "blob"
        and item["path"].endswith(".md")
        and not item["path"].split("/")[-1].startswith(("_", "template"))
    }


def get_repo_sha(owner: str, repo: str, branch: str = "main") -> str:
    """Return the latest commit SHA for the branch."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{branch}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()["sha"]


def fetch_file(owner: str, repo: str, path: str, branch: str = "main") -> str:
    """Fetch raw markdown content for a single file."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def chunk_markdown(content: str, source_file: str) -> list[str]:
    """Split markdown into sections by ## or ### headers, filtering short fragments."""
    sections = re.split(r"\n(?=#{1,3} )", content)
    chunks = []
    for section in sections:
        text = section.strip()
        if len(text) >= CHUNK_MIN_CHARS:
            chunks.append(text)
    # If the whole file produced no valid chunks, treat it as one chunk
    if not chunks and content.strip():
        chunks = [content.strip()]
    return chunks


def category_from_path(file_path: str) -> str:
    """Derive category from the top-level directory of the file path."""
    parts = file_path.split("/")
    return parts[0] if len(parts) > 1 else "general"


def build_chunks(owner: str, repo: str, file_paths: list[str], branch: str = "main") -> list[Chunk]:
    """Fetch and chunk a list of files, returning Chunk objects."""
    chunks: list[Chunk] = []
    for path in file_paths:
        try:
            content = fetch_file(owner, repo, path, branch)
            texts = chunk_markdown(content, path)
            category = category_from_path(path)
            for i, text in enumerate(texts):
                chunks.append(Chunk(text=text, source_file=path, category=category, chunk_index=i))
            logger.debug("Chunked %s → %d chunks", path, len(texts))
        except Exception:
            logger.warning("Failed to fetch/chunk %s", path, exc_info=True)
    return chunks
