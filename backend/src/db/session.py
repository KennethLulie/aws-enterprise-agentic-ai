"""
SQLAlchemy session management and connection pooling.

This module provides database connectivity using SQLAlchemy 2.0 patterns with
lazy engine initialization and connection pooling optimized for the demo workload.

The module supports both local development (with optional DATABASE_URL) and
AWS deployment (DATABASE_URL from Secrets Manager via settings).

Connection Pool Settings:
    - pool_size: 5 connections (base pool)
    - max_overflow: 10 additional connections under load
    - pool_pre_ping: True (validates connections before use)
    - pool_recycle: 300 seconds (prevents stale connections from Neon)

Usage:
    # FastAPI dependency injection
    from src.db import get_session
    from sqlalchemy.orm import Session

    @app.get("/items")
    def get_items(session: Session = Depends(get_session)):
        result = session.execute(select(Item)).scalars().all()
        return result

    # Direct engine access (migrations, testing)
    from src.db import get_engine

    engine = get_engine()
    if engine:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))

See Also:
    - src.config.settings for DATABASE_URL configuration
    - SQLAlchemy 2.0 docs: https://docs.sqlalchemy.org/en/20/
"""

from __future__ import annotations

from collections.abc import Generator

import structlog
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

# Module logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Module-Level Singleton
# =============================================================================

_engine: Engine | None = None

# SessionLocal factory - will be bound to engine on first use
SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Engine Management
# =============================================================================


def get_engine() -> Engine | None:
    """
    Get or create the SQLAlchemy engine singleton.

    Creates the engine lazily on first call, then returns the cached instance.
    Uses connection pooling optimized for the Neon PostgreSQL demo workload.

    Returns:
        Engine | None: SQLAlchemy engine if DATABASE_URL is configured,
            None if running in local development without a database.

    Raises:
        ValueError: If running in AWS environment without DATABASE_URL configured.

    Example:
        engine = get_engine()
        if engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                print(result.scalar())
    """
    global _engine

    if _engine is not None:
        return _engine

    settings = get_settings()

    # Check if DATABASE_URL is configured
    if not settings.database_url:
        if settings.is_aws():
            # In AWS, DATABASE_URL must be configured
            raise ValueError(
                "DATABASE_URL is not configured. In AWS environment, "
                "ensure the database-url secret is set in Secrets Manager "
                "and the App Runner service has access to it."
            )
        else:
            # In local development, database is optional
            logger.warning(
                "database_not_configured",
                message="DATABASE_URL not set. Database features disabled.",
                environment=settings.environment,
            )
            return None

    # Create engine with connection pooling
    try:
        _engine = create_engine(
            settings.database_url,
            # Connection pool settings optimized for demo workload
            pool_size=5,  # Base number of connections
            max_overflow=10,  # Additional connections under load
            pool_pre_ping=True,  # Validate connections before use
            pool_recycle=300,  # Recycle connections after 5 minutes
            # Echo SQL for debugging (only in debug mode)
            echo=settings.debug and settings.log_level.upper() == "DEBUG",
        )

        logger.info(
            "database_engine_created",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )

        return _engine

    except Exception as e:
        logger.error(
            "database_engine_creation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


# =============================================================================
# Session Management
# =============================================================================


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Creates a new session for each request and ensures proper cleanup.
    The session is automatically closed after the request completes.

    Yields:
        Session: SQLAlchemy session bound to the engine.

    Raises:
        RuntimeError: If database is not configured (engine is None).

    Example:
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from src.db import get_session

        @app.get("/users/{user_id}")
        def get_user(user_id: int, session: Session = Depends(get_session)):
            user = session.get(User, user_id)
            return user
    """
    engine = get_engine()

    if engine is None:
        raise RuntimeError(
            "Database not configured. Cannot create session. "
            "Ensure DATABASE_URL is set for database operations."
        )

    # Bind SessionLocal to engine if not already bound
    if SessionLocal.kw.get("bind") is None:
        SessionLocal.configure(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# =============================================================================
# Initialization
# =============================================================================


def init_db() -> None:
    """
    Initialize and verify database connection.

    Called during application startup to ensure the database is accessible.
    Logs success or failure for monitoring.

    Raises:
        Exception: If database connection fails.

    Example:
        # In main.py lifespan context manager:
        async def lifespan(app: FastAPI):
            init_db()  # Verify connection on startup
            yield
            # cleanup here
    """
    engine = get_engine()

    if engine is None:
        logger.info(
            "database_init_skipped",
            message="Database not configured, skipping initialization.",
        )
        return

    try:
        # Test connection with a simple query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.scalar()

        logger.info(
            "database_connection_verified",
            message="Successfully connected to database.",
        )

    except Exception as e:
        logger.error(
            "database_connection_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


# =============================================================================
# Cleanup
# =============================================================================


def close_engine() -> None:
    """
    Close the database engine and dispose of connection pool.

    Call this during application shutdown to cleanly release resources.

    Example:
        # In main.py lifespan context manager:
        async def lifespan(app: FastAPI):
            init_db()
            yield
            close_engine()  # Cleanup on shutdown
    """
    global _engine

    if _engine is not None:
        _engine.dispose()
        logger.info("database_engine_closed")
        _engine = None
