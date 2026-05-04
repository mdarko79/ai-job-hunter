from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dep
from ..models import LogORM

router = APIRouter()


@router.get("")
async def list_logs(
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(session_dep),
):
    stmt = select(LogORM).order_by(desc(LogORM.timestamp)).limit(limit)
    if level:
        stmt = stmt.where(LogORM.level == level)
    if source:
        stmt = stmt.where(LogORM.source == source)
    res = await session.execute(stmt)
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "level": l.level,
            "source": l.source,
            "message": l.message,
        }
        for l in res.scalars().all()
    ]
