"""Generate cover letters and form answers.

All public functions follow the convention: (job, cv_text, prefs, ...).
All inputs are defensively coerced — never crash on a string-instead-of-dict.
"""

from __future__ import annotations
import json

from . import ai_service


def _safe_dict(x) -> dict:
    return x if isinstance(x, dict) else {}


def _safe_str(x) -> str:
    return x if isinstance(x, str) else ""


async def generate_cover_letter(
    job,
    cv_text="",
    prefs=None,
    tone: str = "professional",
) -> str:
    job = _safe_dict(job)
    prefs = _safe_dict(prefs)
    cv_text = _safe_str(cv_text)

    if not ai_service._get_client()[0]:
        return _stub_cover_letter(job, prefs)

    system = (
        f"You write {tone}, concise cover letters (max 220 words). "
        "Open with a specific hook tied to the company. Show 2 concrete achievements "
        "from the CV that match the job. Close with a clear call to action. "
        "No fluff, no clichés like 'I am writing to'."
    )
    prompt = json.dumps({
        "candidate": {
            "name": prefs.get("fullName"),
            "preferences": prefs,
            "cv": cv_text[:5000],
        },
        "job": job,
    })
    try:
        out = await ai_service.chat_text(prompt, system=system)
    except Exception:
        out = ""
    return out or _stub_cover_letter(job, prefs)


async def generate_answers(
    job,
    cv_text="",
    prefs=None,
    questions=None,
) -> dict[str, str]:
    """Generate replies to application form questions (e.g. 'Why this company?')."""
    job = _safe_dict(job)
    prefs = _safe_dict(prefs)
    cv_text = _safe_str(cv_text)
    questions = questions or []

    if not questions:
        return {}
    if not ai_service._get_client()[0]:
        return {q: f"(Stub) Reasonable answer for: {q}" for q in questions}

    system = (
        "Answer each application form question in 2-4 sentences, drawing on the CV "
        "and preferences. Return a JSON object: { question: answer }."
    )
    prompt = json.dumps({
        "questions": questions,
        "candidate": prefs,
        "cv": cv_text[:4000],
        "job": {
            "company": job.get("company"),
            "role": job.get("role"),
            "description": (job.get("description") or "")[:2000],
        },
    })
    try:
        result = await ai_service.chat_json(prompt, system=system)
    except Exception:
        result = {}
    if not result:
        return {q: "" for q in questions}
    return {q: str(result.get(q, "")) for q in questions}


def _stub_cover_letter(job: dict, prefs: dict) -> str:
    name = prefs.get("fullName") or "Candidate"
    company = job.get("company", "your team")
    role = job.get("role", "this role")
    tech = ", ".join((prefs.get("preferredTech") or [])[:4]) or "modern web tech"
    return (
        f"Hi {company} team,\n\n"
        f"I'm applying for the {role} position. My background is {tech}, with hands-on AI "
        f"work in production. I've shipped full-stack products end-to-end and would love to "
        f"bring that to {company}.\n\n"
        f"Happy to walk through specifics. Best,\n{name}"
    )
