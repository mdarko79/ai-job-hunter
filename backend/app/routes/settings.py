from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings as app_settings
from ..database import session_dep
from ..models import SettingsORM
from ..schemas import AutoApplyRules, UserPrefs
from ._log import log_event

router = APIRouter()


async def _get_or_create(session: AsyncSession) -> SettingsORM:
    res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    row = res.scalar_one_or_none()
    if row is None:
        row = SettingsORM(id=1, user_prefs={}, auto_apply_rules={})
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.get("/prefs")
async def get_prefs(session: AsyncSession = Depends(session_dep)):
    row = await _get_or_create(session)
    prefs = row.user_prefs or {}
    return prefs or UserPrefs().model_dump()


@router.put("/prefs")
async def update_prefs(
    body: UserPrefs,
    session: AsyncSession = Depends(session_dep),
):
    row = await _get_or_create(session)
    row.user_prefs = body.model_dump()
    row.updated_at = datetime.utcnow()
    await session.commit()
    await log_event(session, "info", "settings", "Updated user preferences")
    return {"ok": True, "prefs": row.user_prefs}


@router.get("/rules")
async def get_rules(session: AsyncSession = Depends(session_dep)):
    row = await _get_or_create(session)
    rules = row.auto_apply_rules or {}
    if not rules:
        rules = AutoApplyRules().model_dump()
    rules["hardLimitMaxPerDay"] = app_settings.max_applications_per_day_hard_limit
    return rules


@router.put("/rules")
async def update_rules(
    body: AutoApplyRules,
    session: AsyncSession = Depends(session_dep),
):
    hard_limit = app_settings.max_applications_per_day_hard_limit
    if body.maxPerDay > hard_limit:
        raise HTTPException(
            400,
            f"maxPerDay must not exceed hard limit of {hard_limit}",
        )

    row = await _get_or_create(session)
    row.auto_apply_rules = body.model_dump()
    row.updated_at = datetime.utcnow()
    await session.commit()
    await log_event(
        session,
        "info",
        "settings",
        f"Updated auto-apply rules (maxPerDay={body.maxPerDay}, enabled={body.enabled})",
    )
    return {"ok": True, "rules": row.auto_apply_rules, "hardLimitMaxPerDay": hard_limit}


@router.get("/limits")
async def get_limits():
    """Expose the system hard ceiling so the UI can clamp the slider correctly."""
    return {
        "maxApplicationsPerDayHardLimit": app_settings.max_applications_per_day_hard_limit
    }
