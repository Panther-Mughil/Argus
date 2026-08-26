"""Async database engine and session factory (SQLAlchemy 2.0).

The URL is configured via ``ARGUS_DATABASE_URL`` (defaults to the local
containerized PostgreSQL from docker-compose/setup.sh).
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from backend.config import settings

engine = create_async_engine(settings.ARGUS_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
