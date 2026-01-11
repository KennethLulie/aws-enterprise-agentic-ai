"""
Database package for SQLAlchemy session management and connection pooling.

This package provides database connectivity for the backend application using
SQLAlchemy 2.0 patterns. It supports both local development (with optional
DATABASE_URL) and AWS deployment (DATABASE_URL from Secrets Manager).

Connection Pool Configuration:
- pool_size: 5 connections (sufficient for demo workload)
- max_overflow: 10 additional connections under load
- pool_pre_ping: True (validates connections before use)
- pool_recycle: 300 seconds (prevents stale connections)

Usage:
    # FastAPI dependency injection (preferred)
    from src.db import get_session

    @app.get("/items")
    def get_items(session: Session = Depends(get_session)):
        return session.execute(select(Item)).scalars().all()

    # Direct engine access (for migrations, testing)
    from src.db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))

    # Initialize database on startup (in main.py lifespan)
    from src.db import init_db

    # Add to lifespan context manager in main.py:
    # async def lifespan(app: FastAPI):
    #     init_db()  # Verifies connection, logs status
    #     yield
    #     # cleanup here

Local Development:
    Without DATABASE_URL set, the database functions will log a warning
    and return None/skip operations gracefully. This allows the application
    to run in "mock" mode for local development without a database.

AWS Deployment:
    When ENVIRONMENT=aws, DATABASE_URL is loaded from AWS Secrets Manager
    (enterprise-agentic-ai/database-url). The connection is to Neon PostgreSQL.

See Also:
    - src.config.settings for DATABASE_URL configuration
    - SQLAlchemy 2.0 docs: https://docs.sqlalchemy.org/en/20/
"""

from src.db.session import (
    SessionLocal,
    close_engine,
    get_engine,
    get_session,
    init_db,
)

__all__ = [
    "get_engine",
    "get_session",
    "SessionLocal",
    "init_db",
    "close_engine",
]
