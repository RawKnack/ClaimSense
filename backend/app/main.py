import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.database import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    has_pgvector = True
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension verified/created in database.")
    except Exception as err:
        logger.warning("Failed to verify/create pgvector extension: %s", err)
        has_pgvector = False

    if not has_pgvector:
        try:
            from app.db.models import PolicyEmbedding
            Base.metadata.remove(PolicyEmbedding.__table__)
            logger.info("Removed PolicyEmbedding table from metadata because pgvector is not available.")
        except Exception as err:
            logger.warning("Failed to remove PolicyEmbedding table from metadata: %s", err)

    Base.metadata.create_all(bind=engine)
    from app.services.policy_rag import load_policy_chunks, seed_policy_embeddings

    load_policy_chunks()

    if has_pgvector:
        from app.db.database import SessionLocal
        db = SessionLocal()
        import sys
        import os
        sys.stderr.write(f"--- STARTING SEEDING --- EMBEDDING_MODE: {os.environ.get('EMBEDDING_MODE')}\n")
        sys.stderr.flush()
        try:
            seed_policy_embeddings(db)
        except Exception as err:
            logger.warning("Failed to execute database seeding on startup: %s", err)
        finally:
            db.close()
    
    db_name = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
    logger.info("Using database: %s", db_name)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
