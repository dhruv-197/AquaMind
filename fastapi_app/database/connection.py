import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# A local install should be dependable without requiring a PostgreSQL server.
# Deployments set DATABASE_URL to their managed PostgreSQL connection explicitly.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aquamind.db")
_ENVIRONMENT = (os.getenv("AQUAMIND_ENVIRONMENT") or "development").strip().lower()

connect_args = {}
engine = None

try:
    if DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True if not DATABASE_URL.startswith("sqlite") else False,
    )
    # Lightweight connectivity probe — never run expensive startup queries.
    with engine.connect() as conn:
        pass
except Exception as e:
    # Production/staging must fail closed: silently running on empty SQLite
    # hides a broken DATABASE_URL and looks like a healthy deploy.
    allow_sqlite_fallback = _ENVIRONMENT in {"development", "test", "demo"}
    if not allow_sqlite_fallback or DATABASE_URL.startswith("sqlite"):
        raise RuntimeError(
            f"Database connection failed for {_ENVIRONMENT!r} "
            f"(url scheme={DATABASE_URL.split(':', 1)[0]!r}). "
            "Fix DATABASE_URL or set AQUAMIND_ENVIRONMENT=development for local SQLite."
        ) from e

    print(f"[Database] Primary database connection failed or driver missing ({type(e).__name__}).")
    print("[Database] Falling back to local SQLite for development only: sqlite:///aquamind.db")
    DATABASE_URL = "sqlite:///aquamind.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that provides a transactional database session.
    Rolls back on errors so Postgres does not leave aborted transactions open.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
