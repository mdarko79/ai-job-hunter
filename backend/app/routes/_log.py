import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LogORM


async def log_event(
    session: AsyncSession,
    level: str,
    source: str,
    message: str,
    *,
    commit: bool = True,
) -> None:
    entry = LogORM(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        level=level,
        source=source,
        message=message,
    )
    session.add(entry)
    if commit:
        await session.commit()
