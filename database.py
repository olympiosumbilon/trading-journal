from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# Sync engine using psycopg (binary driver, no greenlet or event loop issues)
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
