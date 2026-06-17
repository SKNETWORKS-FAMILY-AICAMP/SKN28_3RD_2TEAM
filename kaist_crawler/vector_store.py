from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from .models import Chunk


TOKEN_RE = re.compile(r"[\uac00-\ud7a3A-Za-z0-9]{2,}")
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_HASH_MODEL = "hash-blake2b-token-bucket"


def hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    tokens = TOKEN_RE.findall(text.lower())
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimensions
        sign = -1.0 if digest[4] & 1 else 1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def build_vector_store(
    chunks: list[Chunk],
    output_root: str | Path,
    *,
    collection_name: str | None = None,
    embedding_provider: str = "hash",
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    embedding_batch_size: int = 64,
) -> None:
    output_root = Path(output_root)
    vector_root = output_root / "vector"
    simple_root = vector_root / "simple"
    simple_root.mkdir(parents=True, exist_ok=True)
    simple_path = simple_root / "chunks.jsonl"
    embeddings, embedding_info = embed_texts(
        [chunk.text for chunk in chunks],
        provider=embedding_provider,
        model=embedding_model,
        dimensions=embedding_dimensions,
        batch_size=embedding_batch_size,
    )
    with simple_path.open("w", encoding="utf-8") as f:
        for chunk, embedding in zip(chunks, embeddings):
            payload = chunk.to_dict()
            payload.update(embedding_info)
            payload["embedding"] = embedding
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    try:
        import chromadb  # type: ignore
    except ImportError:
        return

    chroma_path = vector_root / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_path))
    if collection_name is None:
        collection_name = default_collection_name(
            provider=embedding_info["embedding_provider"],
            model=embedding_info["embedding_model"],
            dimensions=embedding_info["embedding_dimensions"],
        )
    collection = client.get_or_create_collection(name=collection_name)
    if not chunks:
        return
    collection.upsert(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=embeddings,
        metadatas=[_safe_metadata(chunk, embedding_info) for chunk in chunks],
    )


def embed_texts(
    texts: list[str],
    *,
    provider: str,
    model: str | None = None,
    dimensions: int | None = None,
    batch_size: int = 64,
) -> tuple[list[list[float]], dict[str, Any]]:
    provider = provider.lower()
    if provider == "hash":
        resolved_dimensions = dimensions or 384
        return [hash_embedding(text, resolved_dimensions) for text in texts], {
            "embedding_provider": "hash",
            "embedding_model": DEFAULT_HASH_MODEL,
            "embedding_dimensions": resolved_dimensions,
        }
    if provider == "openai":
        load_openai_env(Path(".env"))
        resolved_model = model or os.getenv("OPENAI_EMBEDDING_MODEL") or DEFAULT_OPENAI_EMBEDDING_MODEL
        embeddings = openai_embeddings(
            texts,
            model=resolved_model,
            dimensions=dimensions,
            batch_size=batch_size,
        )
        resolved_dimensions = len(embeddings[0]) if embeddings else dimensions
        return embeddings, {
            "embedding_provider": "openai",
            "embedding_model": resolved_model,
            "embedding_dimensions": resolved_dimensions,
        }
    raise ValueError(f"Unsupported embedding provider: {provider}")


def openai_embeddings(
    texts: list[str],
    *,
    model: str,
    dimensions: int | None = None,
    batch_size: int = 64,
) -> list[list[float]]:
    if not texts:
        return []
    load_openai_env(Path(".env"))
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when embedding_provider is openai")
    if batch_size <= 0:
        raise ValueError("embedding_batch_size must be greater than 0")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload: dict[str, Any] = {
            "model": model,
            "input": batch,
            "encoding_format": "float",
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions
        response = _post_openai_embeddings(url, headers, payload)
        data = sorted(response["data"], key=lambda item: item["index"])
        embeddings.extend(item["embedding"] for item in data)
    return embeddings


def _post_openai_embeddings(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
                continue
    raise RuntimeError(f"OpenAI embeddings request failed: {last_error}") from last_error


def load_openai_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_EMBEDDING_MODEL"}:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def default_collection_name(*, provider: str, model: str, dimensions: int | None) -> str:
    model_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", model).strip("_")
    parts = ["graduate_rag", provider, model_slug]
    if dimensions:
        parts.append(str(dimensions))
    return "_".join(parts)


def _safe_metadata(chunk: Chunk, embedding_info: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "doc_id": chunk.doc_id,
        "site": chunk.site,
        "source_url": chunk.source_url,
        "chunk_index": chunk.chunk_index,
        "embedding_provider": embedding_info["embedding_provider"],
        "embedding_model": embedding_info["embedding_model"],
        "embedding_dimensions": embedding_info["embedding_dimensions"],
    }
    for key, value in chunk.metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = json.dumps(value, ensure_ascii=False)
    return metadata
