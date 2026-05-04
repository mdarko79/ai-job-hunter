import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
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

_GRADE_ORDER = {"A": 6, "B": 5, "C": 4, "D": 3, "E": 2, "F": 1}
CV_DIR = Path("uploads/cv")


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


async def _count_today(session: AsyncSession) -> int:
    since = datetime.utcnow() - timedelta(days=1)
    res = await session.execute(
        select(func.count(ApplicationORM.id)).where(
            ApplicationORM.applied_at >= since,
            ApplicationORM.status == "submitted",
        )
    )
    return int(res.scalar() or 0)


def _norm_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def _contains_any(haystack: str, needles: list[str]) -> bool:
    h = haystack.lower()
    return any(n.lower() in h for n in needles if n)


def _contains_all(haystack: str, needles: list[str]) -> bool:
    h = haystack.lower()
    return all(n.lower() in h for n in needles if n)


def _job_blob(job: JobORM) -> str:
    return " ".join([
        job.company or "",
        job.role or "",
        job.location or "",
        job.source or "",
        job.description or "",
        " ".join(job.tech_stack or []),
        job.url or "",
    ]).lower()


def _latest_cv_path() -> str | None:
    if not CV_DIR.exists():
        return None
    files = [p for p in CV_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if not files:
        return None
    return str(max(files, key=lambda p: p.stat().st_mtime))


def _extract_links_from_cv(cv_text: str) -> dict[str, str]:
    cv_text = cv_text or ""
    out: dict[str, str] = {}
    linkedin = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-/%]+", cv_text, re.I)
    github = re.search(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-]+", cv_text, re.I)
    if linkedin:
        v = linkedin.group(0)
        out["linkedin"] = v if v.startswith("http") else f"https://{v}"
    if github:
        v = github.group(0)
        out["github"] = v if v.startswith("http") else f"https://{v}"
    return out


def _passes_auto_rules(job: JobORM, rules: dict) -> tuple[bool, str]:
    """Hard guardrails for auto-apply. Anything failing returns review/skip."""
    min_score = int(rules.get("minMatchScore", 85) or 85)
    if int(job.match_score or 0) < min_score:
        return False, f"match score {job.match_score}% below {min_score}%"

    if job.status in {"applied", "auto-applied", "rejected", "interview"}:
        return False, f"status is {job.status}"

    if not job.url:
        return False, "no application URL"

    work_modes = _norm_list(rules.get("workModes")) or ["remote", "hybrid"]
    if (job.work_mode or "remote") not in work_modes:
        return False, f"work mode {job.work_mode} not allowed"

    if job.work_mode == "hybrid":
        max_days = int(rules.get("maxDaysInOffice", 1) or 1)
        days = int(job.days_in_office or 1)
        if days > max_days:
            return False, f"hybrid requires {days} office days; max is {max_days}"

    if rules.get("requireApprovalLinkedIn", True):
        if "linkedin" in ((job.url or "") + " " + (job.source or "")).lower():
            return False, "LinkedIn requires manual approval"

    company_blacklist = _norm_list(rules.get("blacklistCompanies"))
    if company_blacklist and _contains_any(job.company or "", company_blacklist):
        return False, "company is blacklisted"

    keyword_blacklist = _norm_list(rules.get("blacklistKeywords"))
    if keyword_blacklist and _contains_any(_job_blob(job), keyword_blacklist):
        return False, "blacklisted keyword found"

    required_tech = _norm_list(rules.get("requiredTech"))
    if required_tech and not _contains_all(_job_blob(job), required_tech):
        return False, "missing required tech/skills"

    require_salary = bool(rules.get("requireSalary", False))
    salary_min = job.salary_min
    if require_salary and not salary_min:
        return False, "salary/rate missing and requireSalary is enabled"

    contract_type = job.contract_type or "permanent"
    if salary_min:
        if contract_type == "contract":
            min_rate = int(rules.get("minSalaryContract", 0) or 0)
            if min_rate and int(salary_min) < min_rate:
                return False, f"day rate {salary_min} below {min_rate}"
        else:
            min_salary = int(rules.get("minSalaryPermanent", 0) or 0)
            if min_salary and int(salary_min) < min_salary:
                return False, f"salary {salary_min} below {min_salary}"

    if rules.get("qualityMode") and rules.get("minOverallGrade") and job.overall_grade:
        min_grade = str(rules.get("minOverallGrade", "B")).upper()
        job_grade = str(job.overall_grade).upper()
        if _GRADE_ORDER.get(job_grade, 0) < _GRADE_ORDER.get(min_grade, 0):
            return False, f"grade {job_grade} below {min_grade}"

    return True, "eligible"


async def _already_submitted(session: AsyncSession, job_id: str) -> bool:
    dup = await session.execute(
        select(ApplicationORM.id).where(
            ApplicationORM.job_id == job_id,
            ApplicationORM.status == "submitted",
        )
    )
    return dup.scalar_one_or_none() is not None


async def _save_application_record(
    *,
    session: AsyncSession,
    job: JobORM,
    mode: str,
    status: str,
    cover: str,
    screenshot_url: str | None,
) -> ApplicationORM:
    app = ApplicationORM(
        id=str(uuid.uuid4()),
        job_id=job.id,
        company=job.company,
        role=job.role,
        applied_at=datetime.utcnow(),
        mode=mode,
        status=status,
        cover_letter=cover,
        screenshot_url=screenshot_url,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return app


async def _apply_job_internal(
    *,
    job: JobORM,
    mode: str,
    answers: dict[str, str],
    session: AsyncSession,
    settings_row: SettingsORM | None,
    submit_required: bool = False,
) -> tuple[ApplicationORM, str | None, int]:
    """Fill/submit one job and persist only truthful statuses.

    Important behaviour:
    - status='submitted' is saved only after Playwright detects confirmation.
    - if semi-auto fills a form but does not click Submit, status='draft-ready'.
    - if auto submit cannot be confirmed, an exception is raised and no fake
      submitted application is created.
    """
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}
    prefs = dict((settings_row.user_prefs if settings_row else {}) or {})
    cv_text = settings_row.cv_text if settings_row else ""
    prefs.update(_extract_links_from_cv(cv_text or ""))

    if not prefs.get("fullName"):
        # Avoid cover letters ending with "Candidate" if settings were not saved.
        prefs["fullName"] = "Dariusz Rozanek"

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
    status = "submitted"

    if mode in ("semi-auto", "auto"):
        if not job.url:
            raise RuntimeError("No job URL available")

        cv_path = _latest_cv_path()
        if not cv_path:
            raise RuntimeError("No uploaded CV file found in backend/uploads/cv")

        result = await fill_form(
            url=job.url,
            prefs=prefs,
            cover_letter=cover,
            answers=answers or {},
            cv_path=cv_path,
            submit=(mode == "auto"),
            save_screenshot=bool(rules.get("saveScreenshots", True)),
            headless=bool(rules.get("headlessAutoApply", False)),
            company=job.company or "apply",
        )
        screenshot_url = result.get("screenshotUrl")

        if mode == "auto":
            if not result.get("submitted"):
                job.status = "review-needed"
                job.weak_points = list(job.weak_points or []) + [str(result.get("message") or "External submit not confirmed")]
                await session.commit()
                raise RuntimeError(
                    f"External submit not confirmed: {result.get('message')}"
                    + (f" | screenshot={screenshot_url}" if screenshot_url else "")
                )
            status = "submitted"
            job.status = "auto-applied"
            job.mode = "auto"
        else:
            status = "draft-ready"
            job.status = "draft-ready"
            job.mode = "semi-auto"
    else:
        # Manual means the user is intentionally tracking an application. It does
        # not claim browser evidence. Use this only after manually applying.
        status = "submitted"
        job.status = "applied"
        job.mode = "manual"

    app = await _save_application_record(
        session=session,
        job=job,
        mode=mode,
        status=status,
        cover=cover,
        screenshot_url=screenshot_url,
    )

    # Persist job status after the application record exists.
    await session.commit()

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
            app.ats_pdf_url = pdf_url
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
                application_id=app.id,
                max_stories=2,
            )
            saved = await story_bank.save_stories(session, stories)
            stories_count = len(saved)
        except Exception as exc:
            await log_event(session, "error", "stories", f"Story generation failed: {exc}")

    await log_event(
        session,
        "success",
        "applications",
        f"{status.upper()} {job.role} @ {job.company} ({mode})"
        + (" + screenshot" if screenshot_url else "")
        + (" + ATS PDF" if pdf_url else "")
        + (f" + {stories_count} stories" if stories_count else ""),
    )

    return app, pdf_url, stories_count


@router.get("")
async def list_applications(session: AsyncSession = Depends(session_dep)):
    res = await session.execute(
        select(ApplicationORM).order_by(desc(ApplicationORM.applied_at))
    )
    return [_app_to_dict(a) for a in res.scalars().all()]


@router.post("/apply")
async def apply_to_job(
    body: ApplyRequest,
    session: AsyncSession = Depends(session_dep),
):
    res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    if await _already_submitted(session, body.jobId):
        raise HTTPException(409, "Already submitted to this job")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}

    user_max = int(rules.get("maxPerDay", 10) or 10)
    hard_max = app_settings.max_applications_per_day_hard_limit
    effective_max = min(user_max, hard_max)

    if body.mode == "auto":
        today = await _count_today(session)
        if today >= effective_max:
            raise HTTPException(429, f"Daily auto-apply limit reached ({today}/{effective_max})")
        ok, reason = _passes_auto_rules(job, rules)
        if not ok:
            raise HTTPException(400, f"Auto apply blocked by rules: {reason}")

    try:
        app, pdf_url, stories_count = await _apply_job_internal(
            job=job,
            mode=body.mode,
            answers=body.answers,
            session=session,
            settings_row=settings_row,
            submit_required=(body.mode == "auto"),
        )
    except Exception as exc:
        raise HTTPException(500, f"Apply failed: {exc}") from exc

    return {
        "ok": True,
        "application": _app_to_dict(app),
        "atsPdfUrl": pdf_url,
        "newStories": stories_count,
        "message": "Submitted externally" if app.status == "submitted" and app.mode == "auto" else app.status,
    }


@router.post("/auto-run")
async def run_auto_apply(
    dry_run: bool = Query(False, description="Preview eligible jobs without submitting"),
    limit: int | None = Query(None, ge=1, le=100),
    session: AsyncSession = Depends(session_dep),
):
    """Run real browser auto-apply over existing jobs that pass every guardrail."""
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}

    if not rules.get("enabled", False):
        raise HTTPException(400, "Auto Apply Mode is disabled in Rules")

    user_max = int(rules.get("maxPerDay", 10) or 10)
    hard_max = app_settings.max_applications_per_day_hard_limit
    effective_max = min(user_max, hard_max)
    applied_today = await _count_today(session)
    remaining = max(0, effective_max - applied_today)

    if remaining <= 0:
        await log_event(session, "warn", "auto-apply", f"Daily auto-apply limit reached ({applied_today}/{effective_max})")
        return {
            "ok": True,
            "dryRun": dry_run,
            "applied": 0,
            "eligible": 0,
            "skipped": 0,
            "remainingToday": 0,
            "message": f"Daily limit reached ({applied_today}/{effective_max})",
            "results": [],
            "skips": [],
        }

    run_limit = min(remaining, limit or remaining)
    min_score = int(rules.get("minMatchScore", 85) or 85)

    res = await session.execute(
        select(JobORM)
        .where(JobORM.match_score >= min_score)
        .where(~JobORM.status.in_(["applied", "auto-applied", "rejected", "interview"]))
        .order_by(desc(JobORM.match_score), desc(JobORM.posted_at))
        .limit(500)
    )
    jobs = res.scalars().all()

    submitted_res = await session.execute(
        select(ApplicationORM.job_id).where(ApplicationORM.status == "submitted")
    )
    submitted_job_ids = {str(x) for x in submitted_res.scalars().all()}

    eligible: list[JobORM] = []
    skips: list[dict] = []
    for job in jobs:
        if job.id in submitted_job_ids:
            skips.append({"jobId": job.id, "role": job.role, "company": job.company, "reason": "already submitted"})
            continue
        ok, reason = _passes_auto_rules(job, rules)
        if ok:
            eligible.append(job)
        else:
            skips.append({"jobId": job.id, "role": job.role, "company": job.company, "reason": reason})

    selected = eligible[:run_limit]

    if dry_run:
        await log_event(session, "info", "auto-apply", f"Dry run: {len(selected)} eligible jobs; {len(skips)} skipped")
        return {
            "ok": True,
            "dryRun": True,
            "applied": 0,
            "eligible": len(eligible),
            "selected": len(selected),
            "skipped": len(skips),
            "remainingToday": remaining,
            "message": f"Dry run found {len(eligible)} eligible jobs",
            "results": [
                {
                    "jobId": j.id,
                    "role": j.role,
                    "company": j.company,
                    "matchScore": j.match_score,
                    "url": j.url,
                }
                for j in selected
            ],
            "skips": skips[:50],
        }

    await log_event(
        session,
        "info",
        "auto-apply",
        f"Starting REAL browser auto-apply for {len(selected)} jobs ({applied_today}/{effective_max} already today)",
    )

    results: list[dict] = []
    failed: list[dict] = []

    for job in selected:
        try:
            app, pdf_url, stories_count = await _apply_job_internal(
                job=job,
                mode="auto",
                answers={},
                session=session,
                settings_row=settings_row,
                submit_required=True,
            )
            results.append({
                "jobId": job.id,
                "applicationId": app.id,
                "role": job.role,
                "company": job.company,
                "matchScore": job.match_score,
                "status": app.status,
                "screenshotUrl": app.screenshot_url,
                "atsPdfUrl": pdf_url,
                "newStories": stories_count,
            })
        except Exception as exc:
            failed.append({
                "jobId": job.id,
                "role": job.role,
                "company": job.company,
                "reason": str(exc),
            })
            await log_event(session, "error", "auto-apply", f"Failed REAL auto-apply for {job.role} @ {job.company}: {exc}")

    await log_event(
        session,
        "success" if results else "warn",
        "auto-apply",
        f"Real auto-apply finished: {len(results)} confirmed submitted, {len(failed)} failed, {len(skips)} skipped",
    )

    return {
        "ok": True,
        "dryRun": False,
        "applied": len(results),
        "eligible": len(eligible),
        "selected": len(selected),
        "failed": len(failed),
        "skipped": len(skips),
        "remainingToday": max(0, remaining - len(results)),
        "message": f"Confirmed submitted: {len(results)}",
        "results": results,
        "failedItems": failed[:50],
        "skips": skips[:50],
    }


@router.get("/stats/today")
async def today_stats(session: AsyncSession = Depends(session_dep)):
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}
    user_max = int(rules.get("maxPerDay", 10) or 10)
    hard_max = app_settings.max_applications_per_day_hard_limit

    return {
        "appliedToday": await _count_today(session),
        "userMaxPerDay": user_max,
        "hardLimit": hard_max,
        "effectiveLimit": min(user_max, hard_max),
    }
