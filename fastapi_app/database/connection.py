import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# A local install should be dependable without requiring a PostgreSQL server.
# Deployments set DATABASE_URL to their managed PostgreSQL connection explicitly.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aquamind.db")

connect_args = {}
engine = None

try:
    if DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True if not DATABASE_URL.startswith("sqlite") else False
    )
    # Test database compilation and connection
    with engine.connect() as conn:
        pass
except Exception as e:
    print(f"[Database] Primary database connection failed or driver missing ({str(e)}).")
    print("[Database] Automatically falling back to local SQLite: sqlite:///aquamind.db")
    DATABASE_URL = "sqlite:///aquamind.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency that provides a transactional database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
