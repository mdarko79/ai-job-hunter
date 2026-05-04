import asyncio
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dep
from ..models import JobORM, SettingsORM
from ..services.job_scraper import fetch_all
from ..services.match_scorer import score_job, _heuristic_score
from ..services import dimensional_scorer
from ._log import log_event

router = APIRouter()

# Fast mode:
# 1) scrape many sources concurrently,
# 2) score every job with cheap heuristic immediately,
# 3) use AI only for the best-looking jobs.
# This avoids 200-600 slow AI calls per search.
_SCRAPER_CONCURRENCY = 25
_AI_SCORE_TOP_N = 60
_AI_SCORE_CONCURRENCY = 6
_AI_MIN_HEURISTIC_FOR_AI = 65
_DIM_SCORE_TOP_N = 12
_EXISTING_ID_CHUNK = 800


def _job_to_dict(j: JobORM) -> dict:
    return {
        "id": j.id,
        "company": j.company,
        "role": j.role,
        "location": j.location,
        "workMode": j.work_mode,
        "daysInOffice": j.days_in_office,
        "salaryMin": j.salary_min,
        "salaryMax": j.salary_max,
        "salaryCurrency": j.salary_currency,
        "contractType": j.contract_type,
        "rateSuffix": j.rate_suffix,
        "matchScore": j.match_score,
        "strongMatches": j.strong_matches or [],
        "weakPoints": j.weak_points or [],
        "recommendation": j.recommendation,
        "status": j.status,
        "mode": j.mode,
        "source": j.source,
        "postedAt": j.posted_at.isoformat() if j.posted_at else None,
        "description": j.description,
        "techStack": j.tech_stack or [],
        "url": j.url,
        "dimensions": j.dimensions,
        "overallGrade": j.overall_grade,
    }


async def _get_existing_ids(session: AsyncSession, ids: list[str]) -> set[str]:
    """Fetch existing job IDs in chunks to avoid one SQL query per job."""
    if not ids:
        return set()

    existing: set[str] = set()
    for i in range(0, len(ids), _EXISTING_ID_CHUNK):
        chunk = ids[i:i + _EXISTING_ID_CHUNK]
        res = await session.execute(select(JobORM.id).where(JobORM.id.in_(chunk)))
        existing.update(str(x) for x in res.scalars().all())
    return existing


_SOFTWARE_TITLE_KEYWORDS = [
    "software", "developer", "engineer", "full stack", "full-stack", "fullstack",
    "backend", "back-end", "frontend", "front-end", "react", "next.js", "nextjs",
    "typescript", "javascript", "python", "node", "fastapi", "django", "flask",
    "ai", "ml", "machine learning", "llm", "rag", "data engineer", "platform engineer",
    "web3", "blockchain", "solidity", "smart contract", "devops", "cloud", "sre",
]

_BANNED_TITLE_KEYWORDS = [
    "barista", "cafe", "coffee", "starbucks", "store associate", "retail associate",
    "warehouse", "driver", "courier", "picker", "packer", "shift lead", "shift supervisor",
    "inventory", "supply chain", "delivery operations", "operations analyst", "allocation analyst",
    "merchandising", "customer service", "sales associate", "account executive", "recruiter",
]

_US_LOCATION_MARKERS = [
    "united states", "usa", " u.s.", " us ", "remote us", "us remote", "north america",
    " ca", " ny", " tx", " fl", " wa", " ma", " il", " pa", " va", " ga", " nc", " az",
    "california", "new york", "texas", "florida", "washington", "massachusetts",
    "illinois", "pennsylvania", "virginia", "georgia", "north carolina", "arizona",
    "philadelphia", "chicago", "pittsburgh", "concord", "richmond", "san francisco",
    "new york", "boston", "seattle", "austin", "denver", "los angeles",
]

_UK_EU_LOCATION_MARKERS = [
    "uk", "united kingdom", "england", "scotland", "wales", "ireland", "europe", "emea",
    "london", "manchester", "birmingham", "leeds", "bristol", "cardiff", "wrexham",
    "poland", "germany", "france", "spain", "netherlands", "portugal", "czech", "remote",
    "worldwide", "global", "anywhere",
]


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _text_for_job(raw: dict) -> tuple[str, str, str, str]:
    role = _norm(raw.get("role"))
    location = _norm(raw.get("location"))
    mode = _norm(raw.get("workMode"))
    tech = " ".join(_norm(t) for t in (raw.get("techStack") or []))
    desc = _norm(raw.get("description"))[:2500]
    return role, location, mode, f"{role} {tech} {desc}"


def _phrase_in_text(phrase: str, text: str) -> bool:
    phrase = _norm(phrase)
    if not phrase:
        return False
    # flexible enough for full-stack/full stack/fullstack, next.js/nextjs etc.
    variants = {phrase, phrase.replace("-", " "), phrase.replace(" ", ""), phrase.replace(".", "")}
    text_flat = text.replace("-", " ").replace(".", "")
    return any(v and (v in text or v in text_flat) for v in variants)


def _allowed_location_and_mode(raw: dict, prefs: dict) -> tuple[bool, str]:
    role, location, mode, _ = _text_for_job(raw)
    if not mode:
        mode = "remote"

    if mode == "onsite" and not bool(prefs.get("onsite", False)):
        return False, "onsite disabled in preferences"
    if mode == "hybrid" and not bool(prefs.get("hybrid", True)):
        return False, "hybrid disabled in preferences"
    if mode == "remote" and not bool(prefs.get("remote", True)):
        return False, "remote disabled in preferences"

    preferred_locations = " ".join(_norm(x) for x in (prefs.get("locations") or []))
    wants_uk_eu = any(x in preferred_locations for x in ["uk", "europe", "eu", "emea"])
    loc_is_us = any(marker in f" {location} " for marker in _US_LOCATION_MARKERS)
    loc_is_uk_eu = any(marker in location for marker in _UK_EU_LOCATION_MARKERS)

    # User preference here is UK/EU Remote. Do not keep US onsite/hybrid/US-only remote roles.
    if wants_uk_eu and loc_is_us and not loc_is_uk_eu:
        return False, "US location does not match UK/EU preference"

    if mode in {"onsite", "hybrid"} and wants_uk_eu and location and not loc_is_uk_eu:
        return False, "hybrid/onsite location outside preferred region"

    return True, ""


def _is_relevant_job(raw: dict, prefs: dict) -> tuple[bool, str]:
    role, location, mode, text = _text_for_job(raw)

    ok_location, why_location = _allowed_location_and_mode(raw, prefs)
    if not ok_location:
        return False, why_location

    # Hard reject obvious non-tech/non-developer roles.
    if any(term in role for term in _BANNED_TITLE_KEYWORDS):
        return False, "non-tech job title"

    target_roles = [_norm(r) for r in (prefs.get("targetRoles") or []) if _norm(r)]
    preferred_tech = [_norm(t) for t in (prefs.get("preferredTech") or []) if _norm(t)]

    role_matches_target = any(_phrase_in_text(r, role) for r in target_roles)
    role_matches_software = any(_phrase_in_text(k, role) for k in _SOFTWARE_TITLE_KEYWORDS)
    tech_matches = sum(1 for t in preferred_tech if _phrase_in_text(t, text))

    # Strong pass: title is directly relevant.
    if role_matches_target or role_matches_software:
        return True, "role/title match"

    # Weaker pass: enough preferred tech in the listing, even if the title is broad.
    if tech_matches >= 2:
        return True, "tech stack match"

    return False, "no target role or tech match"



@router.get("")
async def list_jobs(
    status: Optional[str] = Query(None),
    min_match: int = Query(0, ge=0, le=100),
    session: AsyncSession = Depends(session_dep),
):
    stmt = select(JobORM).order_by(desc(JobORM.posted_at))
    if status:
        stmt = stmt.where(JobORM.status == status)
    if min_match:
        stmt = stmt.where(JobORM.match_score >= min_match)
    res = await session.execute(stmt)
    return [_job_to_dict(j) for j in res.scalars().all()]


@router.post("/clear")
async def clear_jobs(
    keep_applied: bool = True,
    session: AsyncSession = Depends(session_dep),
):
    """Wipe jobs table. Optionally keep ones already applied to."""
    from sqlalchemy import delete

    if keep_applied:
        stmt = delete(JobORM).where(
            ~JobORM.status.in_(["applied", "auto-applied"])
        )
    else:
        stmt = delete(JobORM)
    res = await session.execute(stmt)
    await session.commit()
    return {"ok": True, "deleted": res.rowcount}


@router.post("/search")
async def search_jobs(session: AsyncSession = Depends(session_dep)):
    """Pull fresh jobs from public sources, score them fast, and store them."""
    started = time.perf_counter()

    res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = res.scalar_one_or_none()
    cv_text = settings_row.cv_text if settings_row else None
    prefs = (settings_row.user_prefs if settings_row else {}) or {}
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}

    wellfound_cookie = None
    if rules.get("enableWellfound") and rules.get("wellfoundCookie"):
        wellfound_cookie = rules["wellfoundCookie"]
    multi_dim = bool(rules.get("multiDimScoring"))

    await log_event(session, "info", "search", "Starting job search...")

    # 1) Scrape broadly, then hard-filter against your settings before saving.
    # This keeps the large source coverage but stops irrelevant jobs like Barista/Cafe Manager.
    raw_jobs = await fetch_all(
        "",
        wellfound_cookie=wellfound_cookie,
        concurrent_limit=_SCRAPER_CONCURRENCY,
    )
    await log_event(session, "info", "search", f"Scraped {len(raw_jobs)} jobs from sources")

    if not raw_jobs:
        await log_event(session, "warn", "search", "No jobs returned by scrapers")
        return {"ok": True, "added": 0, "jobs": []}

    relevant_raws: list[dict] = []
    filtered_out = 0
    seen_ids: set[str] = set()
    for raw in raw_jobs:
        raw_id = str(raw.get("id") or "")
        if not raw_id or raw_id in seen_ids:
            continue
        seen_ids.add(raw_id)
        keep, _reason = _is_relevant_job(raw, prefs)
        if keep:
            relevant_raws.append(raw)
        else:
            filtered_out += 1

    await log_event(
        session,
        "info",
        "search",
        f"Filtered to {len(relevant_raws)} relevant jobs; skipped {filtered_out} irrelevant jobs",
    )

    if not relevant_raws:
        elapsed = round(time.perf_counter() - started, 1)
        await log_event(session, "warn", "search", f"No relevant jobs after filters ({elapsed}s)")
        return {"ok": True, "added": 0, "jobs": []}

    # 2) Remove duplicates already in DB with one batched lookup, not N queries.
    raw_ids = [str(r.get("id")) for r in relevant_raws if r.get("id")]
    existing_ids = await _get_existing_ids(session, raw_ids)
    new_raws = [r for r in relevant_raws if r.get("id") and str(r["id"]) not in existing_ids]

    if not new_raws:
        elapsed = round(time.perf_counter() - started, 1)
        await log_event(session, "info", "search", f"No new relevant jobs found ({elapsed}s)")
        return {"ok": True, "added": 0, "jobs": []}

    # 3) Cheap deterministic score for ALL jobs. This is instant.
    heuristic_pairs: list[tuple[dict, dict]] = []
    for raw in new_raws:
        heuristic_pairs.append((raw, _heuristic_score(prefs, raw)))

    # 4) AI-score only the best candidates, not every scraped job.
    ai_candidates = [
        (raw, heuristic)
        for raw, heuristic in sorted(
            heuristic_pairs,
            key=lambda x: int(x[1].get("matchScore", 0)),
            reverse=True,
        )
        if int(heuristic.get("matchScore", 0)) >= _AI_MIN_HEURISTIC_FOR_AI
    ][:_AI_SCORE_TOP_N]

    await log_event(
        session,
        "info",
        "search",
        f"Scoring {len(ai_candidates)} top jobs with AI; saving {len(new_raws)} total jobs",
    )

    sem = asyncio.Semaphore(_AI_SCORE_CONCURRENCY)

    async def ai_score_one(raw: dict, fallback: dict) -> tuple[str, dict]:
        async with sem:
            try:
                scored = await score_job(raw, cv_text or "", prefs)
            except Exception:
                scored = fallback
            if not isinstance(scored, dict) or "matchScore" not in scored:
                scored = fallback
            return str(raw["id"]), scored

    ai_results = await asyncio.gather(
        *[ai_score_one(raw, heuristic) for raw, heuristic in ai_candidates]
    ) if ai_candidates else []
    ai_map = {jid: scored for jid, scored in ai_results}

    # 5) Optional dimensional scoring only for the very top AI candidates.
    dim_map: dict[str, dict] = {}
    if multi_dim:
        dim_candidates = [raw for raw, _ in ai_candidates[:_DIM_SCORE_TOP_N]]

        async def dim_one(raw: dict):
            async with sem:
                try:
                    result = await dimensional_scorer.score_dimensions(
                        raw, cv_text or "", prefs
                    )
                    return str(raw["id"]), result
                except Exception:
                    return str(raw["id"]), {}

        dim_results = await asyncio.gather(*[dim_one(r) for r in dim_candidates])
        dim_map = {jid: r for jid, r in dim_results if r}

    # 6) Persist all jobs. Top jobs get AI score; others get heuristic score.
    saved = 0
    preview_jobs: list[dict] = []

    for raw, heuristic in heuristic_pairs:
        raw_id = str(raw["id"])
        scored = ai_map.get(raw_id, heuristic)
        dim_result = dim_map.get(raw_id, {})
        dim_grades = dim_result.get("grades") if dim_result else None
        overall_grade = dim_result.get("overallGrade") if dim_result else None

        if multi_dim and overall_grade and rules.get("qualityMode"):
            scored["matchScore"] = dimensional_scorer.grade_to_match_score(overall_grade)

        match_score = int(scored.get("matchScore", 0) or 0)
        job = JobORM(
            id=raw_id,
            company=raw.get("company", ""),
            role=raw.get("role", ""),
            location=raw.get("location", ""),
            work_mode=raw.get("workMode", "remote"),
            days_in_office=raw.get("daysInOffice"),
            salary_min=raw.get("salaryMin"),
            salary_max=raw.get("salaryMax"),
            salary_currency=raw.get("salaryCurrency", "£"),
            contract_type=raw.get("contractType", "permanent"),
            rate_suffix=raw.get("rateSuffix"),
            match_score=match_score,
            strong_matches=scored.get("strongMatches", []),
            weak_points=scored.get("weakPoints", []),
            recommendation=scored.get("recommendation", "review"),
            status="ready" if match_score >= 80 else "new",
            mode="manual",
            source=raw.get("source", ""),
            posted_at=raw.get("postedAt") or datetime.utcnow(),
            description=raw.get("description"),
            tech_stack=raw.get("techStack", []),
            url=raw.get("url"),
            dimensions=dim_grades,
            overall_grade=overall_grade,
        )
        session.add(job)
        if len(preview_jobs) < 50:
            preview_jobs.append(_job_to_dict(job))
        saved += 1

    await session.commit()
    elapsed = round(time.perf_counter() - started, 1)
    await log_event(
        session,
        "success",
        "search",
        f"Fetched {saved} new jobs in {elapsed}s; AI scored {len(ai_map)}",
    )
    return {"ok": True, "added": saved, "aiScored": len(ai_map), "elapsedSeconds": elapsed, "jobs": preview_jobs}


@router.post("/{job_id}/reject")
async def reject_job(job_id: str, session: AsyncSession = Depends(session_dep)):
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    job.status = "rejected"
    await session.commit()
    await log_event(session, "info", "jobs", f"Rejected {job.role} @ {job.company}")
    return {"ok": True}


@router.get("/{job_id}")
async def get_job(job_id: str, session: AsyncSession = Depends(session_dep)):
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_dict(job)
