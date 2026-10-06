from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()


def get_db():
    """FastAPI dependency: one session per request, always closed after,
    unlike get_session() which scripts open/close manually themselves."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
