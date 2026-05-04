"""Score how well a job matches the user's CV + preferences.

Dynamic version: it follows Settings. If targetRoles are developer/AI roles,
it scores tech jobs highly and rejects non-tech noise. If targetRoles are
Barista/Cleaner/etc, it scores those roles instead.
"""

from __future__ import annotations
import json
import re

from . import ai_service


def _safe_dict(x) -> dict:
    return x if isinstance(x, dict) else {}


def _safe_str(x) -> str:
    return x if isinstance(x, str) else ""


async def score_job(job, cv_text="", prefs=None) -> dict:
    """Returns dict with: matchScore (0-100), strongMatches, weakPoints, recommendation."""
    job = _safe_dict(job)
    prefs = _safe_dict(prefs)
    cv_text = _safe_str(cv_text)

    baseline = _heuristic_score(prefs, job)

    if not ai_service._get_client()[0]:
        return baseline

    system = (
        "You are an expert recruiter. Score how well a candidate matches a job. "
        "Return JSON: { matchScore: 0-100 integer, strongMatches: [string,..], "
        "weakPoints: [string,..], recommendation: 'apply'|'review'|'reject', "
        "reasoning: '1-2 sentences' }. Be strict. The user's targetRoles, preferredTech, "
        "work mode, salary and location preferences are hard requirements. Penalise heavily "
        "when the job title/role type does not match the configured targetRoles."
    )

    payload = {
        "preferences": prefs,
        "cv": cv_text[:6000],
        "job": {
            "company": job.get("company"),
            "role": job.get("role"),
            "location": job.get("location"),
            "workMode": job.get("workMode"),
            "daysInOffice": job.get("daysInOffice"),
            "salaryMin": job.get("salaryMin"),
            "salaryMax": job.get("salaryMax"),
            "contractType": job.get("contractType"),
            "techStack": job.get("techStack", []),
            "description": (job.get("description") or "")[:2500],
        },
    }
    try:
        result = await ai_service.chat_json(prompt=json.dumps(payload), system=system)
    except Exception:
        result = {}
    if not result or "matchScore" not in result:
        return baseline

    try:
        match_score = int(result.get("matchScore", baseline["matchScore"]))
    except Exception:
        match_score = baseline["matchScore"]

    # Safety cap: if deterministic rules say the role is a mismatch, do not let AI inflate it too high.
    if baseline["recommendation"] == "reject" and baseline["matchScore"] < 40:
        match_score = min(match_score, 45)

    return {
        "matchScore": max(0, min(100, match_score)),
        "strongMatches": result.get("strongMatches", baseline["strongMatches"]),
        "weakPoints": result.get("weakPoints", baseline["weakPoints"]),
        "recommendation": result.get("recommendation", baseline["recommendation"]),
    }


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _has(text: str, phrase: str) -> bool:
    text = _norm(text)
    phrase = _norm(phrase)
    if not phrase:
        return False
    variants = {phrase, phrase.replace("-", " "), phrase.replace(" ", ""), phrase.replace(".", "")}
    text_flat = text.replace("-", " ").replace(".", "")
    return any(v and (v in text or v in text_flat) for v in variants)


_TECH_HINTS = [
    "software", "developer", "engineer", "full stack", "full-stack", "fullstack",
    "backend", "back-end", "frontend", "front-end", "react", "next.js", "nextjs",
    "typescript", "javascript", "python", "node", "fastapi", "django", "flask",
    "ai", "ml", "machine learning", "llm", "rag", "data engineer", "platform engineer",
    "web3", "blockchain", "solidity", "smart contract", "devops", "cloud", "sre",
]

_NON_TECH_NOISE_FOR_TECH_PROFILE = [
    "barista", "cafe", "coffee", "starbucks", "warehouse", "driver", "courier",
    "supply chain", "delivery operations", "inventory", "retail", "sales associate",
    "customer service", "store manager", "shift supervisor", "account executive", "recruiter",
]


def _prefs_terms(prefs: dict) -> tuple[list[str], list[str]]:
    target_roles = [_norm(r) for r in (prefs.get("targetRoles") or []) if _norm(r)]
    preferred_tech = [_norm(t) for t in (prefs.get("preferredTech") or []) if _norm(t)]
    return target_roles, preferred_tech


def _is_tech_profile(prefs: dict) -> bool:
    target_roles, preferred_tech = _prefs_terms(prefs)
    blob = " ".join(target_roles + preferred_tech)
    return any(_has(blob, k) for k in _TECH_HINTS)


def _heuristic_score(prefs: dict, job: dict) -> dict:
    """Dynamic deterministic scoring fallback.

    This follows Settings instead of being permanently hardcoded for developer jobs.
    """
    if not isinstance(prefs, dict):
        prefs = {}
    if not isinstance(job, dict):
        job = {}

    role = _norm(job.get("role"))
    location = _norm(job.get("location"))
    work_mode = _norm(job.get("workMode")) or "remote"
    desc = _norm(job.get("description"))[:2500]
    tech_text = " ".join(_norm(t) for t in (job.get("techStack") or []))
    all_text = f"{role} {tech_text} {desc}"

    target_roles, pref_tech = _prefs_terms(prefs)
    tech_profile = _is_tech_profile(prefs)

    strong: list[str] = []
    weak: list[str] = []
    score = 20

    role_target_hits = [r for r in target_roles if _has(role, r)]
    text_target_hits = [r for r in target_roles if _has(all_text, r)]
    tech_hits = [t for t in pref_tech if _has(all_text, t)]

    if tech_profile and any(term in role for term in _NON_TECH_NOISE_FOR_TECH_PROFILE):
        return {
            "matchScore": 5,
            "strongMatches": [],
            "weakPoints": ["Non-tech / non-developer role for current tech-focused settings"],
            "recommendation": "reject",
        }

    if role_target_hits:
        score += 45
        strong.append(f"Target role match: {role_target_hits[0]}")
    elif text_target_hits:
        score += 30
        strong.append(f"Target role mentioned: {text_target_hits[0]}")
    elif tech_profile and any(_has(role, t) for t in _TECH_HINTS):
        score += 28
        strong.append("Relevant tech/software title")
    else:
        score -= 20
        weak.append("Job title does not match target roles")

    if tech_hits:
        # For tech: preferred stack. For non-tech: preferred skills/tools.
        score += min(25, len(set(tech_hits)) * (5 if tech_profile else 8))
        strong.extend(list(dict.fromkeys(tech_hits))[:6])
    elif pref_tech:
        weak.append("No clear preferred skill/tech overlap")

    # Work mode + location rules
    if work_mode == "onsite" and not prefs.get("onsite", False):
        score -= 35
        weak.append("Onsite disabled in preferences")
    elif work_mode == "hybrid" and not prefs.get("hybrid", True):
        score -= 25
        weak.append("Hybrid not enabled")
    elif work_mode == "remote" and prefs.get("remote", True):
        score += 8
        strong.append("Remote")

    days = job.get("daysInOffice")
    max_days = prefs.get("maxDaysInOffice") or prefs.get("max_days_in_office")
    try:
        if work_mode == "hybrid" and days is not None and max_days is not None and int(days) > int(max_days):
            score -= 20
            weak.append(f"Hybrid requires {days} office days")
    except Exception:
        pass

    preferred_locations = " ".join(_norm(x) for x in (prefs.get("locations") or []))
    wants_uk_eu = any(x in preferred_locations for x in ["uk", "europe", "eu", "emea"])
    us_markers = [
        "united states", "usa", " us ", " ca", " ny", " tx", " fl", " pa", " il", " va",
        "philadelphia", "chicago", "pittsburgh", "concord", "richmond", "san francisco",
    ]
    uk_eu_markers = [
        "uk", "united kingdom", "england", "wales", "scotland", "europe", "emea",
        "london", "manchester", "remote", "worldwide", "global", "anywhere",
    ]
    loc_is_us = any(m in f" {location} " for m in us_markers)
    loc_is_uk_eu = any(m in location for m in uk_eu_markers)
    if wants_uk_eu and loc_is_us and not loc_is_uk_eu:
        score -= 30
        weak.append("US location, not UK/EU remote")

    salary_min = job.get("salaryMin") or 0
    contract = job.get("contractType")
    if contract == "permanent" and salary_min and salary_min < (prefs.get("minSalaryPermanent") or 0):
        score -= 15
        weak.append(f"Salary below minimum ({salary_min})")
    if contract == "contract" and salary_min and salary_min < (prefs.get("minSalaryContract") or 0):
        score -= 15
        weak.append(f"Day rate below minimum ({salary_min})")

    score = max(0, min(100, int(score)))
    rec = "apply" if score >= 80 else ("review" if score >= 60 else "reject")
    return {
        "matchScore": score,
        "strongMatches": strong[:8],
        "weakPoints": weak[:8],
        "recommendation": rec,
    }
