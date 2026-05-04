"""Multi-dimensional A-F scoring inspired by career-ops.

Instead of a single match_score 0-100, this scores each job across 10 weighted
dimensions on an A-F scale. Gives a more honest picture than a single percentage.

A=excellent, B=good, C=acceptable, D=concerning, E=poor, F=disqualifying.

Default weights below sum to 1.0 — adjust in user_prefs if needed.
"""

from __future__ import annotations

import json
from typing import Any

from .ai_service import chat_json

DIMENSIONS = [
    ("roleFit",          "How well the job title and responsibilities match candidate's target roles"),
    ("techStackFit",     "Overlap between job's required tech and candidate's preferred/known tech"),
    ("seniorityFit",     "Whether seniority level matches candidate's experience"),
    ("compFit",          "Whether compensation meets or beats candidate's minimums"),
    ("locationFit",      "Match between job location/work-mode and candidate's preferences"),
    ("cultureFit",       "Inferred company culture vs. candidate's values"),
    ("growthTrajectory", "Career growth potential — promotion path, scope expansion"),
    ("learningOpp",      "How much the candidate would learn — new tech, new domain"),
    ("companyHealth",    "Company stability — funding, headcount, longevity, recent layoffs"),
    ("applicationCost",  "How hard/expensive the application process is — interviews, take-homes"),
]

DEFAULT_WEIGHTS = {
    "roleFit": 0.18,
    "techStackFit": 0.16,
    "seniorityFit": 0.10,
    "compFit": 0.14,
    "locationFit": 0.12,
    "cultureFit": 0.06,
    "growthTrajectory": 0.08,
    "learningOpp": 0.06,
    "companyHealth": 0.06,
    "applicationCost": 0.04,
}

GRADE_TO_NUM = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
NUM_TO_GRADE = {5: "A", 4: "B", 3: "C", 2: "D", 1: "E", 0: "F"}


def _heuristic_dimensions(job: dict[str, Any], cv_text: str, prefs: dict[str, Any]) -> dict[str, str]:
    """Best-effort scoring without LLM — used as fallback."""
    cv_lower = (cv_text or "").lower()
    job_text = f"{job.get('role','')} {job.get('description','')} {' '.join(job.get('techStack') or [])}".lower()

    grades: dict[str, str] = {}

    # roleFit
    target_roles = [r.lower() for r in (prefs.get("targetRoles") or [])]
    role_text = (job.get("role") or "").lower()
    role_hits = sum(1 for tr in target_roles if any(w in role_text for w in tr.split()))
    grades["roleFit"] = "A" if role_hits >= 2 else "B" if role_hits == 1 else "C"

    # techStackFit
    pref_tech = [t.lower() for t in (prefs.get("preferredTech") or [])]
    job_tech = [t.lower() for t in (job.get("techStack") or [])]
    overlap = len(set(pref_tech) & set(job_tech))
    grades["techStackFit"] = "A" if overlap >= 4 else "B" if overlap >= 2 else "C" if overlap == 1 else "D"

    # seniorityFit — guess from role title
    senior_words = ["senior", "staff", "lead", "principal", "head"]
    junior_words = ["junior", "intern", "graduate", "entry"]
    if any(w in role_text for w in senior_words):
        grades["seniorityFit"] = "B"
    elif any(w in role_text for w in junior_words):
        grades["seniorityFit"] = "C"
    else:
        grades["seniorityFit"] = "B"

    # compFit
    sal_min = job.get("salaryMin") or 0
    contract = job.get("contractType", "permanent")
    min_perm = prefs.get("minSalaryPermanent") or 0
    min_contract = prefs.get("minSalaryContract") or 0
    threshold = min_contract if contract == "contract" else min_perm
    if not threshold:
        grades["compFit"] = "C"
    elif sal_min >= threshold * 1.2:
        grades["compFit"] = "A"
    elif sal_min >= threshold:
        grades["compFit"] = "B"
    elif sal_min >= threshold * 0.8:
        grades["compFit"] = "D"
    elif sal_min == 0:
        grades["compFit"] = "C"  # not disclosed
    else:
        grades["compFit"] = "F"

    # locationFit
    work_mode = job.get("workMode", "")
    pref_modes = prefs.get("workModes") or {"remote": True}
    if work_mode == "remote" and pref_modes.get("remote"):
        grades["locationFit"] = "A"
    elif work_mode == "hybrid" and pref_modes.get("hybrid"):
        max_office = prefs.get("maxDaysInOffice", 5)
        days = job.get("daysInOffice") or 2
        grades["locationFit"] = "B" if days <= max_office else "D"
    elif work_mode == "onsite" and pref_modes.get("onsite"):
        grades["locationFit"] = "C"
    else:
        grades["locationFit"] = "E"

    # cultureFit / growth / learning / company / appCost — heuristics are weak,
    # default to "C" without LLM context
    grades["cultureFit"] = "C"
    grades["growthTrajectory"] = "C"
    grades["learningOpp"] = "B" if overlap < len(job_tech) else "C"
    grades["companyHealth"] = "C"
    grades["applicationCost"] = "C"

    return grades


async def score_dimensions(
    job: dict[str, Any],
    cv_text: str,
    prefs: dict[str, Any],
) -> dict[str, Any]:
    """Score a job across all dimensions. Returns {grades, overallGrade, rationale}."""

    # First get heuristic grades as fallback
    fallback = _heuristic_dimensions(job, cv_text, prefs)

    if not cv_text:
        weighted = _weighted_grade(fallback, DEFAULT_WEIGHTS)
        return {
            "grades": fallback,
            "overallGrade": weighted,
            "rationale": {},
            "method": "heuristic",
        }

    # LLM-based scoring
    dimensions_block = "\n".join(
        f"- {key}: {desc}" for key, desc in DIMENSIONS
    )
    system = (
        "You are an honest career advisor evaluating job fit across multiple dimensions. "
        "Give A-F grades. A=excellent, B=good, C=acceptable, D=concerning, E=poor, F=disqualifying. "
        "Be calibrated — most jobs should be B/C, A is rare."
    )
    user = f"""Score this job across 10 dimensions for the candidate.

DIMENSIONS:
{dimensions_block}

CANDIDATE PREFERENCES:
{json.dumps(prefs, default=str)[:1500]}

CANDIDATE CV (first 3000 chars):
{(cv_text or '')[:3000]}

JOB:
Company: {job.get('company','')}
Role: {job.get('role','')}
Location: {job.get('location','')} ({job.get('workMode','')})
Salary: {job.get('salaryMin','?')}-{job.get('salaryMax','?')} {job.get('salaryCurrency','')}
Tech stack: {', '.join(job.get('techStack') or [])}
Description: {(job.get('description') or '')[:3000]}

Return JSON of this exact shape:
{{
  "grades": {{
    "roleFit": "A|B|C|D|E|F",
    "techStackFit": "...",
    "seniorityFit": "...",
    "compFit": "...",
    "locationFit": "...",
    "cultureFit": "...",
    "growthTrajectory": "...",
    "learningOpp": "...",
    "companyHealth": "...",
    "applicationCost": "..."
  }},
  "rationale": {{
    "roleFit": "one sentence why",
    "techStackFit": "one sentence why",
    "compFit": "one sentence why"
  }}
}}
Only include rationale for dimensions where the grade is A or worse than C."""

    try:
        result = await chat_json(system, user)
        grades = result.get("grades") or {}
        # Validate: all dimensions present, all grades A-F
        cleaned: dict[str, str] = {}
        for key, _ in DIMENSIONS:
            g = (grades.get(key) or "").upper()
            cleaned[key] = g if g in GRADE_TO_NUM else fallback[key]
        rationale = {k: str(v)[:300] for k, v in (result.get("rationale") or {}).items()}
        weighted = _weighted_grade(cleaned, DEFAULT_WEIGHTS)
        return {
            "grades": cleaned,
            "overallGrade": weighted,
            "rationale": rationale,
            "method": "llm",
        }
    except Exception:
        return {
            "grades": fallback,
            "overallGrade": _weighted_grade(fallback, DEFAULT_WEIGHTS),
            "rationale": {},
            "method": "heuristic-fallback",
        }


def _weighted_grade(grades: dict[str, str], weights: dict[str, float]) -> str:
    """Compute weighted average grade."""
    total = 0.0
    weight_sum = 0.0
    for key, grade in grades.items():
        w = weights.get(key, 0)
        total += GRADE_TO_NUM.get(grade, 0) * w
        weight_sum += w
    if weight_sum == 0:
        return "C"
    avg = total / weight_sum
    rounded = round(avg)
    return NUM_TO_GRADE.get(rounded, "C")


def grade_to_match_score(grade: str) -> int:
    """Map a letter grade to an approximate 0-100 match score for UI compatibility."""
    return {"A": 92, "B": 78, "C": 62, "D": 45, "E": 28, "F": 10}.get(grade, 50)


def passes_quality_threshold(overall: str, min_grade: str = "B") -> bool:
    """Check if a job's overall grade passes the user's quality filter."""
    return GRADE_TO_NUM.get(overall, 0) >= GRADE_TO_NUM.get(min_grade, 4)
