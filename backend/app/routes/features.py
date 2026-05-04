"""Routes for opt-in 'quality' features — Story Bank + ATS PDF + dimensional scoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dep
from ..models import JobORM, SettingsORM, StoryORM
from ..services import ats_pdf, dimensional_scorer, story_bank
from ._log import log_event

router = APIRouter()


# -------- Story Bank ----------

@router.get("/stories")
async def list_stories(session: AsyncSession = Depends(session_dep)):
    res = await session.execute(select(StoryORM).order_by(desc(StoryORM.created_at)))
    return [story_bank.story_to_dict(s) for s in res.scalars().all()]


@router.get("/stories/master")
async def list_master_stories(session: AsyncSession = Depends(session_dep)):
    res = await session.execute(
        select(StoryORM).where(StoryORM.is_master == True).order_by(desc(StoryORM.times_used))
    )
    return [story_bank.story_to_dict(s) for s in res.scalars().all()]


class StoryToggle(BaseModel):
    isMaster: bool


@router.put("/stories/{story_id}/master")
async def toggle_master(
    story_id: str,
    body: StoryToggle,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(StoryORM).where(StoryORM.id == story_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Story not found")
    s.is_master = body.isMaster
    await session.commit()
    return {"ok": True, "story": story_bank.story_to_dict(s)}


@router.delete("/stories/{story_id}")
async def delete_story(
    story_id: str,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(StoryORM).where(StoryORM.id == story_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Story not found")
    await session.delete(s)
    await session.commit()
    return {"ok": True}


class GenerateStoriesRequest(BaseModel):
    jobId: str | None = None
    applicationId: str | None = None


@router.post("/stories/generate")
async def generate_stories(
    body: GenerateStoriesRequest,
    session: AsyncSession = Depends(session_dep),
):
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = (s.cv_text if s else "") or ""
    if not cv_text:
        raise HTTPException(400, "Upload a CV first")

    if body.jobId:
        res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(404, "Job not found")
        job_dict = {
            "company": job.company,
            "role": job.role,
            "description": job.description or "",
            "techStack": job.tech_stack or [],
        }
    else:
        job_dict = {"company": "", "role": "general", "description": "", "techStack": []}

    stories = await story_bank.generate_stories_for_application(
        cv_text, job_dict, body.applicationId or "manual", max_stories=2,
    )
    saved = await story_bank.save_stories(session, stories)
    await log_event(session, "info", "stories", f"Generated {len(saved)} new stories")
    return {"ok": True, "stories": [story_bank.story_to_dict(s) for s in saved]}


# -------- ATS PDF generation ----------

class GenerateATSRequest(BaseModel):
    jobId: str


@router.post("/ats-pdf")
async def generate_ats_pdf(
    body: GenerateATSRequest,
    session: AsyncSession = Depends(session_dep),
):
    job_res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = (s.cv_text if s else "") or ""

    job_dict = {
        "company": job.company,
        "role": job.role,
        "description": job.description or "",
        "techStack": job.tech_stack or [],
    }
    result = await ats_pdf.generate_ats_cv(cv_text, job_dict)
    await log_event(
        session, "success", "ats",
        f"Generated ATS CV for {job.role} @ {job.company} "
        f"({len(result.get('keywordsUsed', []))} keywords)",
    )
    return {"ok": True, **result}


# -------- Dimensional scoring (manual rescore) ----------

class RescoreRequest(BaseModel):
    jobId: str


@router.post("/dimensional-score")
async def rescore_dimensions(
    body: RescoreRequest,
    session: AsyncSession = Depends(session_dep),
):
    job_res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    s = settings_res.scalar_one_or_none()
    cv_text = (s.cv_text if s else "") or ""
    prefs = (s.user_prefs if s else {}) or {}

    job_dict = {
        "company": job.company,
        "role": job.role,
        "description": job.description or "",
        "techStack": job.tech_stack or [],
        "salaryMin": job.salary_min,
        "salaryMax": job.salary_max,
        "salaryCurrency": job.salary_currency,
        "contractType": job.contract_type,
        "workMode": job.work_mode,
        "daysInOffice": job.days_in_office,
        "location": job.location,
    }
    result = await dimensional_scorer.score_dimensions(job_dict, cv_text, prefs)

    job.dimensions = result["grades"]
    job.overall_grade = result["overallGrade"]
    # Also refresh the legacy match_score so old UI still works
    job.match_score = dimensional_scorer.grade_to_match_score(result["overallGrade"])
    await session.commit()
    await log_event(
        session, "info", "scoring",
        f"Rescored {job.role} @ {job.company} -> {result['overallGrade']} ({result['method']})",
    )
    return {"ok": True, **result}
