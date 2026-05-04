from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from .config import settings
from .models import Base

# ── SQLite-specific tuning ────────────────────────────────────────────────────
# aiosqlite opens one connection per coroutine by default, which causes
# "database is locked" errors when concurrent requests (search, poll-logs,
# etc.) collide.  Two changes fix this:
#
#   1.  StaticPool  — reuses a single underlying connection so SQLAlchemy
#       never tries to hold two write transactions at once from different
#       pool slots.
#
#   2.  WAL journal mode + a 30-second busy timeout — lets readers proceed
#       during a write, and makes writers wait instead of failing instantly.
#
# For non-SQLite databases (Postgres, etc.) the tuning is skipped.
# ─────────────────────────────────────────────────────────────────────────────

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {"echo": False, "future": True}

if _is_sqlite:
    _engine_kwargs.update(
        {
            "connect_args": {
                "timeout": 30,          # wait up to 30 s for the lock
                "check_same_thread": False,
            },
            "poolclass": StaticPool,
        }
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        """Enable WAL mode and busy timeout at the driver level."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")   # concurrent reads + writes
        cursor.execute("PRAGMA busy_timeout=30000") # 30 s in milliseconds
        cursor.execute("PRAGMA synchronous=NORMAL") # safe + faster than FULL
        cursor.close()

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        yield session


async def session_dep():
    async with SessionLocal() as session:
        yield session
