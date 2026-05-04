from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dep
from ..models import JobORM, SettingsORM
from ..schemas import CoverLetterRequest, MatchRequest
from ..services.cover_letter import generate_answers, generate_cover_letter
from ..services.match_scorer import score_job
from ._log import log_event

router = APIRouter()


@router.post("")
async def rescore_job(
    body: MatchRequest,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = body.cvText or (s.cv_text if s else "") or ""
    prefs = (s.user_prefs if s else {}) or {}

    raw = {
        "company": job.company,
        "role": job.role,
        "description": job.description or "",
        "techStack": job.tech_stack or [],
        "salaryMin": job.salary_min,
        "workMode": job.work_mode,
    }
    scored = await score_job(raw, cv_text, prefs)

    job.match_score = scored.get("matchScore", job.match_score)
    job.strong_matches = scored.get("strongMatches", [])
    job.weak_points = scored.get("weakPoints", [])
    job.recommendation = scored.get("recommendation", "review")
    await session.commit()

    await log_event(session, "info", "match", f"Rescored {job.role} @ {job.company} -> {job.match_score}%")

    return {"ok": True, **scored}


@router.post("/cover-letter")
async def cover_letter_route(
    body: CoverLetterRequest,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = (s.cv_text if s else "") or ""
    prefs = (s.user_prefs if s else {}) or {}

    cover = await generate_cover_letter(
        {
            "company": job.company,
            "role": job.role,
            "description": job.description or "",
            "techStack": job.tech_stack or [],
        },
        cv_text,
        prefs,
        tone=body.tone,
    )

    await log_event(session, "info", "ai", f"Generated cover letter for {job.company}")
    return {"ok": True, "coverLetter": cover}


@router.post("/answers")
async def answers_route(
    job_id: str,
    questions: list[str],
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = (s.cv_text if s else "") or ""
    prefs = (s.user_prefs if s else {}) or {}

    answers = await generate_answers(
        {
            "company": job.company,
            "role": job.role,
            "description": job.description or "",
        },
        cv_text,
        prefs,
        questions,
    )
    return {"ok": True, "answers": answers}
