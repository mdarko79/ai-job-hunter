"""Score how well a job matches the user's CV + preferences.

Convention: score_job(job, cv_text, prefs) — same as all other services.
"""

from __future__ import annotations
import json

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

    # Heuristic baseline so things still work without an API key
    baseline = _heuristic_score(prefs, job)

    if not ai_service._get_client()[0]:
        return baseline

    system = (
        "You are an expert technical recruiter. Score how well a candidate matches a job. "
        "Return JSON: { matchScore: 0-100 integer, strongMatches: [string,..], "
        "weakPoints: [string,..], recommendation: 'apply'|'review'|'reject', "
        "reasoning: '1-2 sentences' }. Be honest. Penalise heavily when work mode, location, "
        "or salary clearly don't fit user preferences."
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

    return {
        "matchScore": int(result.get("matchScore", baseline["matchScore"])),
        "strongMatches": result.get("strongMatches", baseline["strongMatches"]),
        "weakPoints": result.get("weakPoints", baseline["weakPoints"]),
        "recommendation": result.get("recommendation", baseline["recommendation"]),
    }


def _norm(value) -> str:
    import re
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _has(text: str, phrase: str) -> bool:
    text = _norm(text)
    phrase = _norm(phrase)
    if not phrase:
        return False
    variants = {phrase, phrase.replace("-", " "), phrase.replace(" ", ""), phrase.replace(".", "")}
    text_flat = text.replace("-", " ").replace(".", "")
    return any(v and (v in text or v in text_flat) for v in variants)


def _heuristic_score(prefs: dict, job: dict) -> dict:
    """Stricter deterministic scoring fallback.

    Old version started at 60, so irrelevant jobs could look acceptable.
    This one starts lower and only gives high scores to target-role/software jobs.
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

    target_roles = [_norm(r) for r in (prefs.get("targetRoles") or []) if _norm(r)]
    pref_tech = [_norm(t) for t in (prefs.get("preferredTech") or []) if _norm(t)]

    software_terms = [
        "software", "developer", "engineer", "full stack", "full-stack", "fullstack",
        "backend", "frontend", "front end", "back end", "react", "next.js", "nextjs",
        "typescript", "javascript", "python", "node", "fastapi", "ai", "ml", "llm", "rag",
        "data engineer", "platform engineer", "web3", "blockchain", "solidity", "devops", "cloud",
    ]
    banned_terms = [
        "barista", "cafe", "coffee", "starbucks", "warehouse", "driver", "courier",
        "supply chain", "delivery operations", "inventory", "retail", "sales associate",
        "customer service", "store manager", "shift supervisor",
    ]

    strong: list[str] = []
    weak: list[str] = []
    score = 25

    if any(term in role for term in banned_terms):
        return {
            "matchScore": 5,
            "strongMatches": [],
            "weakPoints": ["Non-tech / non-developer role"],
            "recommendation": "reject",
        }

    target_hit = any(_has(role, r) for r in target_roles)
    software_hit = any(_has(role, t) for t in software_terms)
    tech_hits = [t for t in pref_tech if _has(all_text, t)]

    if target_hit:
        score += 35
        strong.append("Target role match")
    elif software_hit:
        score += 25
        strong.append("Software/developer title match")
    else:
        score -= 20
        weak.append("Job title does not match target roles")

    if tech_hits:
        score += min(25, len(set(tech_hits)) * 5)
        strong.extend(list(dict.fromkeys(tech_hits))[:6])
    else:
        weak.append("No clear preferred tech overlap")

    # Work mode + location
    if work_mode == "onsite" and not prefs.get("onsite", False):
        score -= 35
        weak.append("Onsite only")
    elif work_mode == "hybrid" and not prefs.get("hybrid", True):
        score -= 25
        weak.append("Hybrid not enabled")
    elif work_mode == "remote" and prefs.get("remote", True):
        score += 8
        strong.append("Remote")

    preferred_locations = " ".join(_norm(x) for x in (prefs.get("locations") or []))
    wants_uk_eu = any(x in preferred_locations for x in ["uk", "europe", "eu", "emea"])
    us_markers = ["united states", "usa", " us ", " ca", " ny", " tx", " fl", " pa", " il", "va", "philadelphia", "chicago", "pittsburgh", "concord", "richmond"]
    uk_eu_markers = ["uk", "united kingdom", "england", "wales", "scotland", "europe", "emea", "london", "manchester", "remote", "worldwide", "global"]
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

