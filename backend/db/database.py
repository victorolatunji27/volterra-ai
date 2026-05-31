# Async SQLAlchemy engine and session factory; exposes get_db dependency for FastAPI.
import os
from typing import AsyncGenerator
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

# Build the connection URL at runtime so special characters in the password
# (: and @) are percent-encoded by quote_plus rather than embedded raw.
_password = quote_plus(os.getenv("DB_PASSWORD", ""))
DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('DB_USER')}:{_password}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
