"""RAG over policy terms + adjudication rules (not claim history)."""

from __future__ import annotations

import json
import logging
import re
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 400


@dataclass
class PolicyChunk:
    chunk_id: str
    source: str
    text: str
    keywords: set[str]


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)}


def _chunk_text(source: str, text: str, prefix: str) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    words = text.split()
    for i in range(0, len(words), CHUNK_SIZE // 4):
        segment = " ".join(words[i : i + CHUNK_SIZE // 4])
        if len(segment) < 40:
            continue
        chunk_id = f"{prefix}_{len(chunks)}"
        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                source=source,
                text=segment,
                keywords=_tokenize(segment),
            )
        )
    return chunks


@lru_cache
def load_policy_chunks() -> list[PolicyChunk]:
    settings = get_settings()
    chunks: list[PolicyChunk] = []

    policy_path = settings.policy_terms_path
    if policy_path.exists():
        policy_json = json.loads(policy_path.read_text(encoding="utf-8"))
        policy_text = json.dumps(policy_json, indent=2)
        chunks.extend(_chunk_text("policy_terms.json", policy_text, "policy"))

    rules_path = settings.adjudication_rules_path
    if rules_path.exists():
        rules_text = rules_path.read_text(encoding="utf-8")
        chunks.extend(_chunk_text("adjudication_rules.md", rules_text, "rules"))

    logger.info("Loaded %s policy RAG chunks", len(chunks))
    return chunks


def seed_policy_embeddings(db: Session) -> None:
    """Generate and store vector embeddings for all policy chunks in PostgreSQL."""
    if os.environ.get("DISABLE_EMBEDDINGS", "").lower() == "true" or os.environ.get("EMBEDDING_MODE", "").lower() == "disabled":
        logger.info("Semantic embeddings are disabled. Skipping seeding.")
        return

    try:
        from app.db.models import PolicyEmbedding
        chunks = load_policy_chunks()
        if not chunks:
            logger.warning("No policy chunks loaded to seed.")
            return

        # Find existing chunk IDs in the database
        existing_ids = {r[0] for r in db.query(PolicyEmbedding.chunk_id).all()}

        to_insert = []
        model = None
        for chunk in chunks:
            if chunk.chunk_id not in existing_ids:
                if model is None:
                    logger.info("Initializing embedding model for seeding...")
                    model = get_embedding_model()
                logger.info("Embedding chunk %s...", chunk.chunk_id)
                vector = model.encode(chunk.text)
                if hasattr(vector, "tolist"):
                    vector = vector.tolist()
                to_insert.append(
                    PolicyEmbedding(
                        chunk_id=chunk.chunk_id,
                        source=chunk.source,
                        text=chunk.text,
                        embedding=vector,
                    )
                )

        if to_insert:
            db.add_all(to_insert)
            db.commit()
            logger.info("Successfully seeded %d policy embeddings to database.", len(to_insert))
        else:
            logger.info("All policy embeddings are already up to date in database.")
    except Exception as exc:
        logger.warning("Failed to seed policy embeddings: %s", exc)


class UnifiedEmbeddingModel:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def encode(self, text: str) -> list[float]:
        import httpx
        key = self.api_key.strip()
        
        # Case 1: OpenRouter key (starts with sk-or-v1-)
        if key.startswith("sk-or-v1-"):
            logger.info("Calling OpenRouter Embedding API (openai/text-embedding-3-small)...")
            url = "https://openrouter.ai/api/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "openai/text-embedding-3-small",
                "input": text,
                "dimensions": 768
            }
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        return data["data"][0]["embedding"]
                logger.warning("OpenRouter Embedding API returned status %d: %s", response.status_code, response.text)
            except Exception as exc:
                logger.warning("OpenRouter Embedding API call failed: %s", exc)

        # Case 2: Standard OpenAI key (starts with sk-)
        elif key.startswith("sk-"):
            logger.info("Calling OpenAI Embedding API (text-embedding-3-small)...")
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "text-embedding-3-small",
                "input": text,
                "dimensions": 768
            }
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        return data["data"][0]["embedding"]
                logger.warning("OpenAI Embedding API returned status %d: %s", response.status_code, response.text)
            except Exception as exc:
                logger.warning("OpenAI Embedding API call failed: %s", exc)

        # Case 3: Google Gemini key
        else:
            logger.info("Calling Google Gemini Embedding API (embedding-001)...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={key}"
            try:
                response = httpx.post(
                    url,
                    json={"content": {"parts": [{"text": text}]}},
                    timeout=15.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if "embedding" in data and "values" in data["embedding"]:
                        return data["embedding"]["values"]
                logger.warning("Gemini Embedding API returned status %d: %s", response.status_code, response.text)
            except Exception as exc:
                logger.warning("Gemini Embedding API call failed: %s", exc)
        
        raise RuntimeError("Failed to generate embedding via API")


@lru_cache
def get_embedding_model():
    import sys
    mode = os.environ.get("EMBEDDING_MODE", "unified").lower()
    sys.stderr.write(f"--- get_embedding_model: mode={mode} ---\n")
    sys.stderr.flush()
    
    settings = get_settings()
    api_key = settings.openai_api_key or settings.gemini_api_key
    if api_key and api_key.strip():
        sys.stderr.write("--- Using UnifiedEmbeddingModel ---\n")
        sys.stderr.flush()
        return UnifiedEmbeddingModel(api_key.strip())
    
    sys.stderr.write("--- Loading SentenceTransformer locally (all-mpnet-base-v2, 768 dimensions) ---\n")
    sys.stderr.flush()
    from sentence_transformers import SentenceTransformer
    logger.info("Loading SentenceTransformer('all-mpnet-base-v2') locally...")
    return SentenceTransformer("all-mpnet-base-v2")


def retrieve_policy_context(
    diagnosis: str | None = None,
    treatment: str | None = None,
    top_k: int = 3,
    db: Session | None = None,
) -> list[dict[str, str]]:
    """Retrieve policy context using semantic vector search or fallback keyword overlap."""
    query_text = f"{diagnosis or ''} {treatment or ''}".strip()
    if not query_text:
        return []

    # Try vector similarity retrieval using pgvector in PostgreSQL
    if db is not None and os.environ.get("DISABLE_EMBEDDINGS", "").lower() != "true" and os.environ.get("EMBEDDING_MODE", "").lower() != "disabled":
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.bind)
            if inspector.has_table("policy_embeddings"):
                from app.db.models import PolicyEmbedding
                
                # Self-healing: Seed on first search request since internet is blocked during startup scan
                try:
                    if db.query(PolicyEmbedding).count() == 0:
                        logger.info("Embeddings table is empty. Running on-demand seeding...")
                        seed_policy_embeddings(db)
                except Exception as seed_err:
                    logger.warning("On-demand seeding check failed: %s", seed_err)

                model = get_embedding_model()
                query_vector = model.encode(query_text)
                if hasattr(query_vector, "tolist"):
                    query_vector = query_vector.tolist()
                
                # Query top_k nearest neighbors by cosine distance
                results = (
                    db.query(PolicyEmbedding)
                    .order_by(PolicyEmbedding.embedding.cosine_distance(query_vector))
                    .limit(top_k)
                    .all()
                )
                if results:
                    logger.info("Successfully retrieved %d chunks via vector search.", len(results))
                    return [
                        {"chunk_id": r.chunk_id, "source": r.source, "text": r.text}
                        for r in results
                    ]
        except Exception as exc:
            logger.warning("Vector retrieval failed, falling back to keyword overlap: %s", exc)

    # Fallback: Keyword overlap retrieval
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    scored: list[tuple[float, PolicyChunk]] = []
    for chunk in load_policy_chunks():
        overlap = len(query_tokens & chunk.keywords)
        if overlap > 0:
            scored.append((overlap / max(len(query_tokens), 1), chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"chunk_id": c.chunk_id, "source": c.source, "text": c.text}
        for _, c in scored[:top_k]
    ]
