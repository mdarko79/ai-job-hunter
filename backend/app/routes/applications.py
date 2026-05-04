import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings as app_settings
from ..database import session_dep
from ..models import ApplicationORM, JobORM, SettingsORM
from ..schemas import ApplyRequest
from ..services.cover_letter import generate_cover_letter
from ..services.playwright_apply import fill_form
from ._log import log_event

router = APIRouter()


def _app_to_dict(a: ApplicationORM) -> dict:
    return {
        "id": a.id,
        "jobId": a.job_id,
        "company": a.company,
        "role": a.role,
        "appliedAt": a.applied_at.isoformat() if a.applied_at else None,
        "mode": a.mode,
        "status": a.status,
        "coverLetter": a.cover_letter,
        "screenshotUrl": a.screenshot_url,
        "atsPdfUrl": a.ats_pdf_url,
    }


@router.get("")
async def list_applications(session: AsyncSession = Depends(session_dep)):
    res = await session.execute(
        select(ApplicationORM).order_by(desc(ApplicationORM.applied_at))
    )
    return [_app_to_dict(a) for a in res.scalars().all()]


async def _count_today(session: AsyncSession) -> int:
    since = datetime.utcnow() - timedelta(days=1)
    res = await session.execute(
        select(func.count(ApplicationORM.id)).where(ApplicationORM.applied_at >= since)
    )
    return int(res.scalar() or 0)


@router.post("/apply")
async def apply_to_job(
    body: ApplyRequest,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    # Block duplicates by job
    dup = await session.execute(
        select(ApplicationORM).where(ApplicationORM.job_id == body.jobId)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(409, "Already applied to this job")

    # Daily limit (only enforced for auto mode)
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}
    prefs = (settings_row.user_prefs if settings_row else {}) or {}
    cv_text = settings_row.cv_text if settings_row else ""

    user_max = int(rules.get("maxPerDay", 10))
    hard_max = app_settings.max_applications_per_day_hard_limit
    effective_max = min(user_max, hard_max)

    if body.mode == "auto":
        today = await _count_today(session)
        if today >= effective_max:
            raise HTTPException(
                429,
                f"Daily auto-apply limit reached ({today}/{effective_max})",
            )

    # Generate cover letter
    cover = await generate_cover_letter(
        {
            "company": job.company,
            "role": job.role,
            "description": job.description or "",
            "techStack": job.tech_stack or [],
        },
        cv_text or "",
        prefs,
    )

    screenshot_url = None
    if job.url and body.mode in ("semi-auto", "auto"):
        try:
            result = await fill_form(
                url=job.url,
                prefs=prefs,
                cover_letter=cover,
                answers=body.answers,
                submit=(body.mode == "auto"),
                save_screenshot=bool(rules.get("saveScreenshots", True)),
            )
            screenshot_url = result.get("screenshotUrl")
        except Exception as exc:
            await log_event(
                session, "error", "playwright",
                f"Auto-fill failed for {job.company}: {exc}",
            )

    application = ApplicationORM(
        id=str(uuid.uuid4()),
        job_id=job.id,
        company=job.company,
        role=job.role,
        applied_at=datetime.utcnow(),
        mode=body.mode,
        status="submitted" if body.mode == "auto" else "submitted",
        cover_letter=cover,
        screenshot_url=screenshot_url,
    )
    session.add(application)

    job.status = "auto-applied" if body.mode == "auto" else "applied"
    job.mode = body.mode

    await session.commit()

    # ---- Optional quality features ----
    pdf_url = None
    stories_count = 0
    if rules.get("autoGenerateATSPDF"):
        try:
            from ..services import ats_pdf
            pdf_result = await ats_pdf.generate_ats_cv(
                cv_text or "",
                {
                    "company": job.company,
                    "role": job.role,
                    "description": job.description or "",
                    "techStack": job.tech_stack or [],
                },
            )
            pdf_url = pdf_result.get("pdfUrl")
            application.ats_pdf_url = pdf_url
            await session.commit()
        except Exception as exc:
            await log_event(session, "error", "ats", f"ATS PDF failed: {exc}")

    if rules.get("autoGenerateStories"):
        try:
            from ..services import story_bank
            stories = await story_bank.generate_stories_for_application(
                cv_text or "",
                {
                    "company": job.company,
                    "role": job.role,
                    "description": job.description or "",
                    "techStack": job.tech_stack or [],
                },
                application_id=application.id,
                max_stories=2,
            )
            saved = await story_bank.save_stories(session, stories)
            stories_count = len(saved)
        except Exception as exc:
            await log_event(session, "error", "stories", f"Story generation failed: {exc}")

    await log_event(
        session, "success", "applications",
        f"Applied to {job.role} @ {job.company} ({body.mode})"
        + (f" + ATS PDF" if pdf_url else "")
        + (f" + {stories_count} stories" if stories_count else ""),
    )

    return {
        "ok": True,
        "application": _app_to_dict(application),
        "atsPdfUrl": pdf_url,
        "newStories": stories_count,
    }


@router.get("/stats/today")
async def today_stats(session: AsyncSession = Depends(session_dep)):
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}
    user_max = int(rules.get("maxPerDay", 10))
    hard_max = app_settings.max_applications_per_day_hard_limit

    return {
        "appliedToday": await _count_today(session),
        "userMaxPerDay": user_max,
        "hardLimit": hard_max,
        "effectiveLimit": min(user_max, hard_max),
    }
