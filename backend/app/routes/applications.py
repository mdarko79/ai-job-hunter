import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings as app_settings
from ..database import session_dep
from ..models import ApplicationORM, JobORM, SettingsORM
from ..schemas import ApplyRequest
from ..services.cover_letter import generate_answers, generate_cover_letter
from ._log import log_event
from ..services.form_question_reader import extract_application_questions

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


async def _count_today(session: AsyncSession, *, include_drafts: bool = False) -> int:
    since = datetime.utcnow() - timedelta(days=1)
    statuses = ["submitted"] if not include_drafts else ["submitted", "draft-ready"]
    res = await session.execute(
        select(func.count(ApplicationORM.id)).where(
            ApplicationORM.applied_at >= since,
            ApplicationORM.status.in_(statuses),
        )
    )
    return int(res.scalar() or 0)


def _norm_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def _contains_any(haystack: str, needles: list[str]) -> bool:
    h = (haystack or "").lower()
    return any(n.lower() in h for n in needles if n)


def _contains_all(haystack: str, needles: list[str]) -> bool:
    h = (haystack or "").lower()
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


def _candidate_profile(settings_row: SettingsORM | None) -> dict:
    prefs = dict((settings_row.user_prefs if settings_row else {}) or {})
    cv_text = (settings_row.cv_text if settings_row else "") or ""
    prefs.update({k: v for k, v in _extract_links_from_cv(cv_text).items() if v})

    # Fallbacks from the uploaded CV so copy/paste packs are usable even if Settings were not saved.
    if not prefs.get("fullName"):
        prefs["fullName"] = "Dariusz Rozanek"
    if not prefs.get("email"):
        email = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", cv_text)
        if email:
            prefs["email"] = email.group(0)
    if not prefs.get("phone"):
        phone = re.search(r"(?:\+44|0)\d[\d\s]{8,}", cv_text)
        if phone:
            prefs["phone"] = phone.group(0).strip()
    if not prefs.get("location"):
        prefs["location"] = "UK"

    # Optional fields. These can be added later to Settings UI. Until then, the answer engine
    # treats them as manual checks instead of guessing sensitive/legal details.
    pronouns = prefs.get("pronouns") or prefs.get("preferredPronouns") or ""
    visa = prefs.get("requiresVisaSponsorship")
    right_to_work_uk = prefs.get("rightToWorkUK")

    return {
        "fullName": prefs.get("fullName") or "",
        "email": prefs.get("email") or "",
        "phone": prefs.get("phone") or "",
        "location": prefs.get("location") or "UK",
        "linkedin": prefs.get("linkedin") or "",
        "github": prefs.get("github") or "",
        "pronouns": pronouns,
        "requiresVisaSponsorship": visa,
        "rightToWorkUK": right_to_work_uk,
        "preferredTech": _norm_list(prefs.get("preferredTech")),
        "targetRoles": _norm_list(prefs.get("targetRoles")),
    }

def _passes_auto_rules(job: JobORM, rules: dict) -> tuple[bool, str]:
    """Guardrails for safe pack preparation. This does NOT submit externally."""
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


async def _get_existing_draft(session: AsyncSession, job_id: str) -> ApplicationORM | None:
    res = await session.execute(
        select(ApplicationORM)
        .where(ApplicationORM.job_id == job_id)
        .where(ApplicationORM.status == "draft-ready")
        .order_by(desc(ApplicationORM.applied_at))
    )
    return res.scalars().first()


async def _count_company_applications(session: AsyncSession, company: str, job_id: str | None = None) -> int:
    stmt = select(func.count(ApplicationORM.id)).where(ApplicationORM.company == company)
    if job_id:
        stmt = stmt.where(ApplicationORM.job_id != job_id)
    res = await session.execute(stmt)
    return int(res.scalar() or 0)


def _extract_keywords(job: JobORM, prefs: dict) -> list[str]:
    text = _job_blob(job)
    preferred = _norm_list(prefs.get("preferredTech"))
    target_roles = _norm_list(prefs.get("targetRoles"))
    found: list[str] = []

    for item in preferred + target_roles + _norm_list(job.tech_stack):
        item_clean = item.strip()
        if item_clean and item_clean.lower() in text and item_clean.lower() not in [x.lower() for x in found]:
            found.append(item_clean)

    common = [
        "AI", "LLM", "RAG", "Agents", "Python", "FastAPI", "React", "Next.js",
        "TypeScript", "Node.js", "PostgreSQL", "Supabase", "WebSockets", "SaaS",
        "Automation", "API", "Cloud", "Docker", "Web3", "Solidity",
    ]
    for item in common:
        if item.lower() in text and item.lower() not in [x.lower() for x in found]:
            found.append(item)

    return found[:8]


def _company_links(job: JobORM) -> dict[str, str]:
    company = job.company or "company"
    domain = ""
    if job.url:
        try:
            parsed = urlparse(job.url)
            domain = parsed.netloc.replace("www.", "")
        except Exception:
            domain = ""

    query_base = quote_plus(company)
    return {
        "jobUrl": job.url or "",
        "companyDomain": domain,
        "aboutSearch": f"https://www.google.com/search?q={query_base}+about",
        "careersSearch": f"https://www.google.com/search?q={query_base}+careers",
        "newsSearch": f"https://www.google.com/search?q={query_base}+latest+news",
    }


def _short_cover(job: JobORM, candidate: dict, keywords: list[str]) -> str:
    name = candidate.get("fullName") or "Dariusz Rozanek"
    tech = ", ".join(keywords[:4]) or "AI-powered full-stack systems"
    company = job.company or "your team"
    role = job.role or "this role"
    return (
        f"Hi {company} team,\n\n"
        f"I'm interested in the {role} role because it closely matches my experience building "
        f"production-ready systems across {tech}. I have delivered SaaS, automation, AI and "
        f"real-time applications end-to-end, and I would be happy to discuss how I can contribute "
        f"to {company}.\n\n"
        f"Best,\n{name}"
    )


def _suggested_answers(job: JobORM, candidate: dict, keywords: list[str]) -> list[dict[str, str]]:
    role = job.role or "this role"
    company = job.company or "your company"
    tech = ", ".join(keywords[:5]) or "full-stack development, AI automation and scalable web systems"
    return [
        {
            "question": "Why are you interested in this role?",
            "answer": (
                f"I'm interested in the {role} role because it aligns with my hands-on experience "
                f"building practical software systems across {tech}. I enjoy owning work end-to-end, "
                f"from architecture through delivery and iteration."
            ),
        },
        {
            "question": "Why this company?",
            "answer": (
                f"{company} looks like a strong fit because the role appears to value practical engineering, "
                f"product thinking and scalable delivery. I would review the company mission and product page "
                f"before submitting, then add one specific sentence about why their product interests me."
            ),
        },
        {
            "question": "Relevant experience",
            "answer": (
                "I have built AI-powered applications, SaaS platforms, automation tools and real-time systems "
                "using technologies such as Next.js, TypeScript, Python, FastAPI, Node.js, PostgreSQL and Supabase. "
                "My work includes LLM features, RAG pipelines, agents, WebSockets, dashboards and production workflows."
            ),
        },
    ]


def _cv_years_experience(cv_text: str) -> float:
    """Best-effort years extraction from CV text, e.g. '3.5+ years'."""
    cv_text = cv_text or ""
    m = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?\s+of\s+experience", cv_text, re.I)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return 0.0
    return 0.0


def _max_office_days(rules: dict) -> int:
    try:
        return int(rules.get("maxDaysInOffice", 1) or 1)
    except Exception:
        return 1


def _question_has_yes_no_options(options: list[str]) -> bool:
    opts = {str(o).strip().lower() for o in (options or [])}
    return "yes" in opts and "no" in opts


def _option_answer(value: str, options: list[str]) -> str:
    """Return the exact option spelling where possible."""
    if not options:
        return value
    for opt in options:
        if str(opt).strip().lower() == value.strip().lower():
            return str(opt).strip()
    return value


def _manual_check(reason: str) -> str:
    return f"MANUAL CHECK: {reason}"


def _open_ended_answer(question: str, job: JobORM, candidate: dict, prefs: dict) -> tuple[str, bool, str] | None:
    """Strong deterministic answers for common application-form essay questions.

    This is intentionally candidate-specific so the app does not fall back to generic
    'manual check' text for high-value questions such as Why us / impact / proof.
    """
    q = re.sub(r"\s+", " ", question or "").strip().lower()
    company = (job.company or "the company").strip()
    role = (job.role or "this role").strip()

    # Company motivation / timing.
    if (q.startswith("why ") and (company.lower() in q or "now" in q or "this company" in q)) or "why elevenlabs" in q:
        if "elevenlabs" in company.lower() or "elevenlabs" in q:
            return (
                "ElevenLabs is one of the most exciting AI companies right now because voice is becoming a core interface for real products, not just a demo. "
                "My background combines full-stack engineering, AI workflows and real-time systems, and I have already used ElevenLabs in a side project to turn generated text into character voice/audio. "
                "The timing feels right because ElevenLabs is expanding from voice generation into agents, enterprise use cases and richer multimodal audio products, which matches the kind of practical AI systems I want to build.",
                False,
                "company motivation template",
            )
        return (
            f"I am interested in {company} because the role connects strongly with the systems I like building: AI-powered products, full-stack execution and practical automation. "
            f"For the {role} role, I can bring hands-on experience shipping Next.js/TypeScript/Python systems, AI integrations and production-focused workflows. "
            "The timing is right because I am looking for a role where I can turn my independent AI/SaaS project experience into impact inside a focused engineering team.",
            False,
            "company motivation template",
        )

    # Most impactful thing built.
    if "most impactful" in q or ("impactful" in q and "built" in q) or "specific contribution" in q:
        return (
            "One of the most impactful things I built was an AI-powered SaaS/workflow automation platform where I owned the full product flow from architecture to frontend, backend APIs and AI integration. "
            "My specific contribution was designing the Next.js/TypeScript interface, building Python/Node backend services, integrating LLM features and structuring the data layer in PostgreSQL/Supabase. "
            "The result was a production-style system that reduced repetitive manual work significantly and gave users a faster way to generate, manage and act on AI-assisted outputs.",
            False,
            "impact template",
        )

    # Success metrics / how it worked.
    if "how did you know" in q or "success actually look" in q or "how did it work" in q:
        return (
            "I knew it worked because the system produced measurable improvements rather than just a working demo. "
            "For my AI generation and automation projects, success meant reducing manual workflow time, improving reliability, keeping the UI fast, and making the output useful enough that a user could take action without rebuilding everything manually. "
            "In practice, that looked like faster generation cycles, fewer manual steps, stable end-to-end flows and clear user-facing outputs such as generated assets, voice, dashboards or application materials.",
            False,
            "success metrics template",
        )

    # ElevenLabs usage.
    if "used elevenlabs" in q or "have you used elevenlabs" in q or ("elevenlabs" in q and ("build" in q or "explore" in q)):
        return (
            "Yes. I used ElevenLabs in my Goblin Gibber side project to generate character-style voice/audio from short AI-generated text. "
            "The project combined text generation, voice synthesis and a game-like web UI, so I explored how voice can make an AI product feel more interactive and memorable. "
            "I also had to think practically about latency, cost control and limiting generated text length so the voice feature stayed usable.",
            False,
            "ElevenLabs usage template",
        )

    # General side project / AI usage.
    if "side project" in q and ("ai" in q or "build" in q or "built" in q):
        return (
            "My strongest side projects are AI and full-stack systems: Goblin Gibber, AIDreamer, GenMint and trading/automation dashboards. "
            "Across these projects I built the frontend, backend APIs, AI integrations and data flows myself, which gave me practical experience turning AI capabilities into usable product features.",
            False,
            "side project template",
        )

    return None


def _structured_form_answer(
    *,
    question: str,
    generated: str,
    job: JobORM,
    prefs: dict,
    rules: dict,
    candidate: dict,
    cv_text: str,
    options: list[str] | None = None,
) -> tuple[str, bool, str]:
    """Deterministic answers for common ATS form questions.

    Returns (answer, review_required, reason). We intentionally avoid guessing legal/sensitive
    items such as visa sponsorship or pronouns unless saved in Settings.
    """
    q_raw = question or ""
    q = re.sub(r"\s+", " ", q_raw).strip().lower()
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    yn = _question_has_yes_no_options(opts)

    # Ignore placeholders / helper text that sometimes gets extracted as a fake field.
    if q in {"start typing", "start typing...", "type here", "type here...", "select", "choose", "please select"}:
        return "", True, "placeholder/noise"

    # Source questions must be handled before generic LinkedIn detection, because labels like
    # 'Social media (LinkedIn, Instagram, X etc)' are asking how you heard about the role,
    # not for your LinkedIn profile URL.
    if ("how did you hear" in q or "where did you hear" in q or q == "source" or "social media" in q or "job board" in q) and "profile" not in q:
        preferred = ["LinkedIn", "Job board", "Company careers page", "Careers page", "Other"]
        for want in preferred:
            for opt in opts:
                if want.lower() in opt.lower():
                    return opt, False, "source option"
        return "LinkedIn", False, "source"

    # Basic candidate fields shown in forms.
    if re.fullmatch(r"(?:first\s*)?name|full name", q):
        return candidate.get("fullName") or "Dariusz Rozanek", False, "candidate name"
    if q in {"email", "email address"}:
        return candidate.get("email") or "", False, "candidate email"
    if q in {"phone", "phone number", "mobile"}:
        return candidate.get("phone") or "", False, "candidate phone"
    if q in {"location", "current location", "where are you located"}:
        loc_answer = candidate.get("location") or prefs.get("location") or "Wrexham, UK"
        if str(loc_answer).strip().lower() == "uk":
            loc_answer = "Wrexham, UK"
        return loc_answer, False, "candidate location"
    if "linkedin" in q and ("profile" in q or "url" in q or "link" in q):
        return candidate.get("linkedin") or _manual_check("Add your LinkedIn URL in Settings first."), not bool(candidate.get("linkedin")), "linkedin profile"
    if "github" in q:
        return candidate.get("github") or _manual_check("Optional. Add GitHub URL in Settings if you want to include it."), not bool(candidate.get("github")), "github"
    if q in {"resume", "cv", "upload resume", "upload cv"} or "resume" in q or "cv" == q:
        cv_path = _latest_cv_path()
        return (f"Upload this file manually: {cv_path}" if cv_path else _manual_check("Upload your CV manually.")), not bool(cv_path), "cv upload"

    # Pronouns are a personal preference. Do not guess.
    if "pronoun" in q:
        saved = str(candidate.get("pronouns") or "").strip()
        if saved:
            return _option_answer(saved, opts), False, "saved pronouns"
        # If the form offers an opt-out/prefer-not option, choose that. Otherwise mark manual.
        for opt in opts:
            lo = opt.lower()
            if "prefer" in lo or "decline" in lo or "not" in lo:
                return opt, False, "prefer not to say"
        return _manual_check("Choose your pronouns manually. Do not let the bot guess this."), True, "pronouns require manual choice"

    # Years / professional web app experience.
    if ("3 years" in q or ">3" in q or "more than 3" in q or "over 3" in q) and any(x in q for x in ["web application", "web app", "software", "professionally", "professional"]):
        years = _cv_years_experience(cv_text)
        ans = "Yes" if years >= 3 else "No"
        return _option_answer(ans, opts), years < 3, f"cv years={years}"
    if "years" in q and "experience" in q and any(x in q for x in ["web", "software", "react", "python", "engineer", "developer"]):
        years = _cv_years_experience(cv_text)
        if years:
            return f"{years:g}+ years", False, "years from CV"

    # Location / UK based.
    loc = (candidate.get("location") or prefs.get("location") or "").lower()
    if any(x in q for x in ["currently based in the uk", "based in uk", "based in the uk", "located in the uk", "live in the uk"]):
        ans = "Yes" if ("uk" in loc or "wrexham" in loc or "united kingdom" in loc) else "No"
        return _option_answer(ans, opts), ans == "No", "location"

    # Visa / sponsorship / right to work: do not guess unless user saved it explicitly.
    if any(x in q for x in ["visa", "sponsor", "sponsorship", "right to work", "authorised", "authorized", "work eligibility"]):
        visa = candidate.get("requiresVisaSponsorship")
        right_uk = candidate.get("rightToWorkUK")
        if visa is not None:
            ans = "Yes" if bool(visa) else "No"
            return _option_answer(ans, opts), False, "saved visa sponsorship preference"
        if right_uk is not None and "uk" in q:
            # If the question is 'do you require sponsorship', rightToWorkUK=True usually means No.
            if any(x in q for x in ["require", "need", "sponsor"]):
                ans = "No" if bool(right_uk) else "Yes"
            else:
                ans = "Yes" if bool(right_uk) else "No"
            return _option_answer(ans, opts), False, "saved UK right-to-work preference"
        return _manual_check("Answer this legally. Choose 'No' only if you do not now or in future require visa sponsorship."), True, "visa/right-to-work manual check"

    # Office / hybrid days.
    if "office" in q or "hybrid" in q or "onsite" in q or "on-site" in q:
        max_days = _max_office_days(rules)
        # detect '4 days a week', '4 days/week', etc.
        day_match = re.search(r"(\d+)\s*(?:days?|d)\s*(?:a|per|/)\s*(?:week|wk)", q)
        if day_match:
            required_days = int(day_match.group(1))
            ans = "Yes" if required_days <= max_days else "No"
            return _option_answer(ans, opts), False, f"office days required={required_days}, max={max_days}"
        if "london" in q and ("willing" in q or "able" in q):
            # User has max office days in rules, so keep answer aligned with that.
            return f"I am open to hybrid work with up to {max_days} day(s) per week in the office.", False, "hybrid preference"
        return f"I am open to remote work and hybrid arrangements with up to {_max_office_days(rules)} day(s) per week in office.", False, "hybrid preference"

    # Salary / availability.
    if any(x in q for x in ["salary", "compensation", "expected pay", "rate"]):
        min_perm = prefs.get("minSalaryPermanent") or 0
        min_contract = prefs.get("minSalaryContract") or 0
        if (job.contract_type or "permanent") == "contract" and min_contract:
            return f"My expected day rate is from £{min_contract}/day, depending on scope, contract length and working arrangement.", False, "salary"
        if min_perm:
            return f"My salary expectation is from £{min_perm} per year, depending on the full package, scope and working arrangement.", False, "salary"
        return "I am open to a market-aligned package based on the role scope, seniority and working arrangement.", False, "salary"
    if any(x in q for x in ["notice", "start date", "available to start", "availability"]):
        return "I am available to discuss a suitable start date and can align around the notice period and project timeline.", False, "availability"

    # Consent/privacy: avoid auto-consenting without review.
    if any(x in q for x in ["privacy", "terms", "consent", "agree", "data processing"]):
        return _manual_check("Review the consent/privacy text yourself before selecting an option."), True, "legal consent manual check"

    # Strong templates for important open-ended questions.
    template = _open_ended_answer(q_raw, job, candidate, prefs)
    if template:
        return template

    # If options are yes/no and the model did not provide a clean option, mark manual instead of vague text.
    if yn and (not generated or generated.lower().startswith("please review")):
        return _manual_check("This is a yes/no question. Review the job/form context and select Yes or No manually."), True, "yes/no manual check"

    clean_generated = (generated or "").strip()
    if clean_generated and not clean_generated.lower().startswith("please review"):
        return clean_generated, False, "ai generated"

    # Last-chance template after LLM failure. This is intentionally better than a blank
    # for copy/paste workflows, but still asks the user to review.
    if any(x in q for x in ["why", "what", "how", "tell", "describe", "experience", "built", "build"]):
        return (
            f"My background is in full-stack and AI engineering, with hands-on experience building products using Next.js, TypeScript, Python, FastAPI, Node.js, Supabase and LLM-based workflows. "
            f"For {job.company or 'your team'}, I would focus on shipping practical, reliable product features and using my independent project experience to contribute quickly.",
            False,
            "generic open-ended fallback",
        )

    return "Please review manually and tailor this answer before submitting.", True, "no generated answer"


def _safe_generated_answer(question: str, generated: str, job: JobORM, prefs: dict) -> str:
    """Backward-compatible wrapper used by older code paths."""
    answer, _, _ = _structured_form_answer(
        question=question,
        generated=generated,
        job=job,
        prefs=prefs,
        rules={},
        candidate={},
        cv_text="",
        options=[],
    )
    return answer


async def _answer_extracted_questions(
    *,
    job: JobORM,
    questions: list[dict],
    settings_row: SettingsORM | None,
) -> list[dict[str, Any]]:
    prefs = dict((settings_row.user_prefs if settings_row else {}) or {})
    rules = dict((settings_row.auto_apply_rules if settings_row else {}) or {})
    cv_text = (settings_row.cv_text if settings_row else "") or ""
    candidate = _candidate_profile(settings_row)
    question_texts = [str(q.get("question") or "").strip() for q in questions if str(q.get("question") or "").strip()]
    if not question_texts:
        return []

    try:
        generated = await generate_answers(
            {
                "company": job.company,
                "role": job.role,
                "description": job.description or "",
                "techStack": job.tech_stack or [],
            },
            cv_text,
            {**prefs, **candidate},
            question_texts,
        )
    except Exception:
        generated = {}

    answered: list[dict[str, Any]] = []
    for q in questions:
        text = str(q.get("question") or "").strip()
        options = q.get("options") or []
        answer, review_required, reason = _structured_form_answer(
            question=text,
            generated=str(generated.get(text, "") or ""),
            job=job,
            prefs=prefs,
            rules=rules,
            candidate=candidate,
            cv_text=cv_text,
            options=options,
        )
        answered.append({
            "question": text,
            "answer": answer,
            "fieldType": q.get("fieldType") or "unknown",
            "required": bool(q.get("required")),
            "options": options,
            "reviewRequired": bool(review_required),
            "reason": reason,
        })
    return answered

async def _build_pack(job: JobORM, settings_row: SettingsORM | None, session: AsyncSession) -> dict:
    prefs = dict((settings_row.user_prefs if settings_row else {}) or {})
    cv_text = (settings_row.cv_text if settings_row else "") or ""
    candidate = _candidate_profile(settings_row)
    keywords = _extract_keywords(job, prefs)
    long_cover = await generate_cover_letter(
        {
            "company": job.company,
            "role": job.role,
            "description": job.description or "",
            "techStack": job.tech_stack or [],
        },
        cv_text,
        {**prefs, **candidate},
        tone="professional",
    )
    short_cover = _short_cover(job, candidate, keywords)
    duplicate_company_count = await _count_company_applications(session, job.company or "", job.id)
    cv_path = _latest_cv_path()

    return {
        "job": {
            "id": job.id,
            "company": job.company,
            "role": job.role,
            "location": job.location,
            "workMode": job.work_mode,
            "matchScore": job.match_score,
            "url": job.url,
            "source": job.source,
        },
        "candidate": candidate,
        "coverLetters": {
            "short": short_cover,
            "long": long_cover,
        },
        "keywords": keywords,
        "suggestedAnswers": _suggested_answers(job, candidate, keywords),
        "links": _company_links(job),
        "cv": {
            "path": cv_path or "",
            "uploaded": bool(cv_path),
            "charactersParsed": len(cv_text),
        },
        "checks": {
            "duplicateCompanyApplications": duplicate_company_count,
            "alreadySubmitted": False,
            "manualSubmitRequired": True,
            "externalSubmitDisabled": True,
        },
        "instructions": [
            "Open the job in your normal browser.",
            "Copy/paste the prepared fields manually.",
            "Submit only after you review the form yourself.",
            "After a real confirmation page or email, click Track manual in the dashboard.",
        ],
    }


async def _save_or_update_draft(
    *,
    session: AsyncSession,
    job: JobORM,
    cover: str,
) -> ApplicationORM:
    existing = await _get_existing_draft(session, job.id)
    if existing:
        existing.cover_letter = cover
        existing.applied_at = datetime.utcnow()
        existing.mode = "semi-auto"
        existing.status = "draft-ready"
        app = existing
    else:
        app = ApplicationORM(
            id=str(uuid.uuid4()),
            job_id=job.id,
            company=job.company,
            role=job.role,
            applied_at=datetime.utcnow(),
            mode="semi-auto",
            status="draft-ready",
            cover_letter=cover,
            screenshot_url=None,
        )
        session.add(app)

    job.status = "draft-ready"
    job.mode = "semi-auto"
    await session.commit()
    await session.refresh(app)
    return app


@router.get("")
async def list_applications(session: AsyncSession = Depends(session_dep)):
    res = await session.execute(
        select(ApplicationORM).order_by(desc(ApplicationORM.applied_at))
    )
    return [_app_to_dict(a) for a in res.scalars().all()]


@router.get("/stats/today")
async def today_stats(session: AsyncSession = Depends(session_dep)):
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}
    user_max = int(rules.get("maxPerDay", 10) or 10)
    hard_max = app_settings.max_applications_per_day_hard_limit
    applied_today = await _count_today(session, include_drafts=False)
    prepared_today = await _count_today(session, include_drafts=True)
    return {
        "appliedToday": applied_today,
        "preparedToday": prepared_today,
        "userMaxPerDay": user_max,
        "hardLimit": hard_max,
        "effectiveLimit": min(user_max, hard_max),
    }


@router.post("/extract-form/{job_id}")
async def extract_form_questions(job_id: str, session: AsyncSession = Depends(session_dep)):
    """Read visible application form questions and generate copy/paste answers.

    Safe mode: this does not fill, click, upload, or submit anything externally.
    """
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.url:
        raise HTTPException(400, "Job has no application URL")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()

    extracted = await extract_application_questions(job.url, headless=False)
    if not extracted.get("ok"):
        await log_event(session, "warn", "applications", f"Could not extract form questions for {job.role} @ {job.company}: {extracted.get('error')}")
        return {
            "ok": False,
            "jobId": job.id,
            "company": job.company,
            "role": job.role,
            "url": job.url,
            "error": extracted.get("error") or "Could not extract form questions",
            "questions": [],
            "answers": [],
        }

    questions = extracted.get("questions") or []
    answers = await _answer_extracted_questions(job=job, questions=questions, settings_row=settings_row)
    await log_event(session, "success", "applications", f"Extracted {len(answers)} form question(s) for {job.role} @ {job.company}")
    return {
        "ok": True,
        "jobId": job.id,
        "company": job.company,
        "role": job.role,
        "url": job.url,
        "title": extracted.get("title") or "",
        "questions": questions,
        "answers": answers,
        "count": len(answers),
        "message": "Questions extracted. Copy/paste answers manually and review before submitting.",
    }


def _looks_like_form_question(line: str) -> bool:
    q = (line or "").strip().lower()
    if not q:
        return False
    if q.endswith("?"):
        return True
    starters = [
        "how ", "what ", "why ", "when ", "where ", "do ", "does ", "did ", "are ", "is ",
        "have ", "can ", "will ", "would ", "please ", "tell ", "describe ", "linkedin",
        "your pronouns", "pronouns", "name", "email", "phone", "resume", "cv",
    ]
    return any(q.startswith(x) for x in starters)


def _is_option_line(line: str) -> bool:
    q = (line or "").strip().lower()
    if not q:
        return False
    common = {
        "yes", "no", "he / him", "she / her", "they / them", "other", "prefer not to say",
        "type here...", "type here", "hello@example.com...", "hello@example.com",
        "no file chosen", "upload file", "or drag and drop here",
        "start typing", "start typing...", "copy", "required",
    }
    return q in common or len(q) <= 35 and not q.endswith("?")


def _split_pasted_questions(text: str) -> list[dict[str, Any]]:
    """Parse a raw copy/paste from an ATS form into questions + options.

    Handles blocks like:
      Have you spent >3 years ... ?\nYes\nNo
      Your Pronouns\nhe / him\nshe / her\nthey / them\nother
    """
    text = (text or "").strip()
    if not text:
        return []
    raw_lines = [re.sub(r"\s+", " ", x).strip(" -•\t") for x in text.splitlines()]
    lines = [x for x in raw_lines if x]

    skip_exact = {
        "type here", "type here...", "hello@example.com", "hello@example.com...",
        "no file chosen", "upload file", "or drag and drop here",
        "start typing", "start typing...", "copy", "required",
    }

    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush():
        nonlocal current
        if current and current.get("question"):
            q = str(current["question"]).strip()
            key = q.lower().strip(" ?:. ")
            if key and key not in {str(x.get("question", "")).lower().strip(" ?:. ") for x in out}:
                out.append(current)
        current = None

    for line in lines:
        lo = line.lower().strip()
        if lo in skip_exact:
            continue

        # Split paragraph-style pasted yes/no questions after question marks.
        parts = [p.strip() for p in re.split(r"(?<=\?)\s+", line) if p.strip()]
        if len(parts) > 1:
            for p in parts:
                if _looks_like_form_question(p):
                    flush()
                    current = {"question": p, "fieldType": "manual", "required": False, "options": []}
            continue

        if _looks_like_form_question(line):
            flush()
            current = {"question": line, "fieldType": "manual", "required": False, "options": []}
            continue

        if current and _is_option_line(line):
            opt = line.strip()
            if opt.lower() not in skip_exact and opt not in current["options"]:
                current["options"].append(opt)
            continue

        # Lines that are neither questions nor options are ignored to avoid noise.

    flush()
    return out[:60]

@router.post("/answer-pasted/{job_id}")
async def answer_pasted_questions(
    job_id: str,
    payload: dict = Body(...),
    session: AsyncSession = Depends(session_dep),
):
    """Generate answers from questions manually pasted by the user. Safest workflow."""
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()

    questions = payload.get("questions")
    if isinstance(questions, list):
        question_objs = [
            {"question": str(q).strip(), "fieldType": "manual", "required": False, "options": []}
            for q in questions
            if str(q).strip()
        ][:40]
    else:
        question_objs = _split_pasted_questions(str(payload.get("text") or ""))

    answers = await _answer_extracted_questions(job=job, questions=question_objs, settings_row=settings_row)
    await log_event(session, "success", "applications", f"Generated {len(answers)} pasted form answer(s) for {job.role} @ {job.company}")
    return {
        "ok": True,
        "jobId": job.id,
        "company": job.company,
        "role": job.role,
        "questions": question_objs,
        "answers": answers,
        "count": len(answers),
        "message": "Answers generated from pasted questions. Copy/paste manually and review before submitting.",
    }


@router.post("/prepare-pack/{job_id}")
async def prepare_application_pack(job_id: str, session: AsyncSession = Depends(session_dep)):
    """Prepare a safe human-in-the-loop application pack. Does not open browser or submit."""
    res = await session.execute(select(JobORM).where(JobORM.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if await _already_submitted(session, job_id):
        raise HTTPException(409, "Already submitted to this job")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()

    pack = await _build_pack(job, settings_row, session)
    app = await _save_or_update_draft(
        session=session,
        job=job,
        cover=pack["coverLetters"]["long"] or pack["coverLetters"]["short"],
    )
    pack["application"] = _app_to_dict(app)

    await log_event(session, "success", "applications", f"Prepared application pack for {job.role} @ {job.company}")
    return {"ok": True, "pack": pack, "message": "Application pack prepared. Review and submit manually."}


@router.post("/apply")
async def apply_to_job(
    body: ApplyRequest,
    session: AsyncSession = Depends(session_dep),
):
    """Manual tracking only. This endpoint does not submit to external ATS platforms."""
    res = await session.execute(select(JobORM).where(JobORM.id == body.jobId))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    if body.mode != "manual":
        raise HTTPException(400, "External submit is disabled. Use Prepare Pack, submit manually, then Track manual.")

    if await _already_submitted(session, body.jobId):
        raise HTTPException(409, "Already submitted to this job")

    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    pack = await _build_pack(job, settings_row, session)
    cover = pack["coverLetters"]["long"] or pack["coverLetters"]["short"]

    draft = await _get_existing_draft(session, job.id)
    if draft:
        draft.mode = "manual"
        draft.status = "submitted"
        draft.cover_letter = cover
        draft.applied_at = datetime.utcnow()
        app = draft
    else:
        app = ApplicationORM(
            id=str(uuid.uuid4()),
            job_id=job.id,
            company=job.company,
            role=job.role,
            applied_at=datetime.utcnow(),
            mode="manual",
            status="submitted",
            cover_letter=cover,
            screenshot_url=None,
        )
        session.add(app)

    job.status = "applied"
    job.mode = "manual"
    await session.commit()
    await session.refresh(app)

    await log_event(session, "success", "applications", f"Tracked manual application to {job.role} @ {job.company}")
    return {
        "ok": True,
        "application": _app_to_dict(app),
        "message": "Tracked as manually submitted. Use this only after you submit on the employer site.",
    }


@router.post("/auto-run")
async def run_auto_apply(
    dry_run: bool = Query(False, description="Preview eligible jobs without preparing packs"),
    limit: int | None = Query(None, ge=1, le=100),
    session: AsyncSession = Depends(session_dep),
):
    """Safe auto-run: prepares application packs only. It never submits external forms."""
    settings_res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    settings_row = settings_res.scalar_one_or_none()
    rules = (settings_row.auto_apply_rules if settings_row else {}) or {}

    if not rules.get("enabled", False):
        raise HTTPException(400, "Auto Apply Mode is disabled in Rules")

    user_max = int(rules.get("maxPerDay", 10) or 10)
    hard_max = app_settings.max_applications_per_day_hard_limit
    effective_max = min(user_max, hard_max)
    prepared_today = await _count_today(session, include_drafts=True)
    remaining = max(0, effective_max - prepared_today)

    if remaining <= 0:
        await log_event(session, "warn", "auto-apply", f"Daily preparation limit reached ({prepared_today}/{effective_max})")
        return {
            "ok": True,
            "dryRun": dry_run,
            "prepared": 0,
            "eligible": 0,
            "skipped": 0,
            "remainingToday": 0,
            "message": f"Daily limit reached ({prepared_today}/{effective_max})",
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
        await log_event(session, "info", "auto-apply", f"Dry run: {len(selected)} packs would be prepared; {len(skips)} skipped")
        return {
            "ok": True,
            "dryRun": True,
            "prepared": 0,
            "eligible": len(eligible),
            "selected": len(selected),
            "skipped": len(skips),
            "remainingToday": remaining,
            "message": f"Dry run found {len(eligible)} eligible jobs. External submit is disabled.",
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
        f"Preparing {len(selected)} safe application packs ({prepared_today}/{effective_max} already today)",
    )

    results: list[dict] = []
    failed: list[dict] = []
    for job in selected:
        try:
            pack = await _build_pack(job, settings_row, session)
            app = await _save_or_update_draft(
                session=session,
                job=job,
                cover=pack["coverLetters"]["long"] or pack["coverLetters"]["short"],
            )
            results.append({
                "jobId": job.id,
                "company": job.company,
                "role": job.role,
                "status": app.status,
                "mode": app.mode,
                "applicationId": app.id,
                "message": "Pack prepared; submit manually",
            })
        except Exception as exc:
            failed.append({"jobId": job.id, "company": job.company, "role": job.role, "error": str(exc)})
            await log_event(session, "error", "auto-apply", f"Pack preparation failed for {job.role} @ {job.company}: {exc}")

    await log_event(session, "success", "auto-apply", f"Prepared {len(results)} packs; {len(failed)} failed")
    return {
        "ok": True,
        "dryRun": False,
        "prepared": len(results),
        "eligible": len(eligible),
        "skipped": len(skips),
        "failed": len(failed),
        "remainingToday": max(0, remaining - len(results)),
        "message": f"Prepared {len(results)} application packs. Submit them manually in your browser.",
        "results": results,
        "failures": failed,
        "skips": skips[:50],
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORM ANSWER OVERRIDES v2.1
# These override earlier helpers at runtime. They are stricter for sensitive
# questions and stronger for AI/LLM job-application questions.
# ─────────────────────────────────────────────────────────────────────────────

def _name_parts(candidate: dict) -> tuple[str, str]:
    full = str(candidate.get("fullName") or "Dariusz Rozanek").strip()
    parts = [p for p in re.split(r"\s+", full) if p]
    if not parts:
        return "Dariusz", "Rozanek"
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _option_contains(options: list[str], needles: list[str]) -> str | None:
    for opt in options or []:
        lo = str(opt).lower()
        if any(n in lo for n in needles):
            return str(opt).strip()
    return None


def _safe_prefer_not_answer(options: list[str]) -> tuple[str, bool, str]:
    opt = _option_contains(options, [
        "prefer not", "decline", "do not wish", "don't wish", "choose not", "not disclose",
        "i don't want", "i do not want", "no answer", "not to say",
    ])
    if opt:
        return opt, False, "prefer not to say option"
    return _manual_check("Sensitive voluntary question. Choose manually; use 'Prefer not to say' if available."), True, "sensitive voluntary manual check"


def _open_ended_answer(question: str, job: JobORM, candidate: dict, prefs: dict) -> tuple[str, bool, str] | None:
    q = re.sub(r"\s+", " ", question or "").strip().lower()
    company = (job.company or "the company").strip()
    role = (job.role or "this role").strip()

    # Company factual lookup questions must not be guessed.
    if "values page" in q or ("how many" in q and "core values" in q):
        return (
            f"MANUAL CHECK: Open {company}'s values page and enter the exact number of core values shown there. Do not guess this answer.",
            True,
            "company factual lookup manual check",
        )

    if "why elevenlabs" in q or ("elevenlabs" in q and "why" in q):
        return (
            "ElevenLabs stands out because voice is becoming a core interface for real products, not just a demo. "
            "My background combines full-stack engineering, AI workflows and real-time systems, and I have already used ElevenLabs in a side project to generate character-style voice/audio from short AI-generated text. "
            "Now is the right time because ElevenLabs is moving from voice generation into broader agent, enterprise and multimodal audio use cases, which matches the practical AI systems I want to build.",
            False,
            "ElevenLabs motivation template",
        )

    if q.startswith("why ") or "why now" in q or "why this" in q or "interested in this role" in q:
        return (
            f"I am interested in {company} because the {role} role aligns with the kind of practical AI and full-stack systems I have been building: product-focused interfaces, backend APIs, automation workflows and reliable AI integrations. "
            "I enjoy owning features end-to-end and turning AI capabilities into usable workflows rather than isolated demos. "
            f"I would bring hands-on experience with Next.js, TypeScript, Python, FastAPI, Node.js, Supabase, RAG, AI agents and real-time systems to help {company} ship useful product improvements quickly.",
            False,
            "company motivation template",
        )

    if "most impactful" in q or ("impact" in q and "built" in q) or "specific contribution" in q:
        return (
            "One of the most impactful things I built was an AI-powered SaaS/workflow automation platform where I owned the product end-to-end: architecture, frontend, backend APIs, AI integration and data model. "
            "My specific contribution was building the Next.js/TypeScript interface, Python/Node backend services, LLM workflows and PostgreSQL/Supabase data layer. "
            "The impact was reducing repetitive manual work and giving users a faster, more reliable way to generate, manage and act on AI-assisted outputs.",
            False,
            "impact template",
        )

    if "how did you know" in q or "success actually look" in q or ("what did success" in q):
        return (
            "I knew it worked because success showed up in practical outcomes, not just a working demo. "
            "For my AI generation and automation projects, I measured success by reduced manual steps, faster generation cycles, stable end-to-end flows, useful outputs and a smoother user experience. "
            "In practice that meant users could move from input to usable output faster, with fewer manual corrections and clearer next actions.",
            False,
            "success metrics template",
        )

    if "used elevenlabs" in q or "have you used elevenlabs" in q or ("elevenlabs" in q and ("build" in q or "explore" in q)):
        return (
            "Yes. I used ElevenLabs in my Goblin Gibber side project to generate character-style voice/audio from short AI-generated text. "
            "The project combined text generation, voice synthesis and a game-like web UI, so I explored how voice can make an AI product feel more interactive and memorable. "
            "I also had to think practically about latency, cost control and limiting generated text length so the feature stayed usable.",
            False,
            "ElevenLabs usage template",
        )

    if "large language model" in q or "llm" in q or "machine learning systems in production" in q:
        return (
            "I have worked with LLM-based systems in production-style projects, including RAG pipelines, AI agents, automation workflows and AI-assisted content/asset generation. "
            "The main operational challenges were reliability, output quality, cost control and observability: LLM outputs can vary, prompts need versioning, long contexts can become expensive, and failures must be visible. "
            "I addressed this with structured prompts, smaller bounded inputs, fallback logic, async processing, logging, manual review for high-risk outputs and practical limits such as reducing generated text length before voice generation to control API usage and latency.",
            False,
            "LLM production template",
        )

    if "shared infrastructure" in q or "platform capabilities" in q or "tooling" in q:
        return (
            "A good example is the infrastructure I built around my AI/web application projects: reusable API routes, async job flows, database models, authentication, dashboards and integration layers for LLM and voice features. "
            "The problem was that AI features often become fragile if every feature is built as a one-off script, so I focused on creating reusable backend services and clear frontend workflows. "
            "The impact was faster iteration, easier debugging and a more reliable product foundation for features such as generation, voice, NFT/data workflows, scoring and user-facing dashboards.",
            False,
            "AI infrastructure template",
        )

    if "remote-first" in q or "distributed" in q or "distributed setting" in q or "high-performing" in q:
        return (
            "Most of my recent work has been built independently and remotely, so I am used to working with clear ownership, written communication and asynchronous delivery. "
            "To stay effective in a distributed setting, I break work into visible milestones, document decisions, keep the product flow testable, and use logs/dashboards to make progress and issues clear. "
            "For a team environment, I would apply the same habits: clear specs, small shippable increments, strong documentation, regular demos and transparent tracking of quality, reliability and user impact.",
            False,
            "remote work template",
        )

    if "using ai in your day-to-day" in q or "changed in the last 12 months" in q:
        return (
            "I use AI daily as an engineering accelerator: planning features, generating and reviewing code, creating test cases, debugging, writing documentation, improving UX copy and producing application materials. "
            "Over the last 12 months, my use has shifted from simple prompting to building AI into actual workflows: agents, RAG-style context, automation pipelines and structured outputs that can be used inside products. "
            "I still treat AI output as something to verify, but it has become a practical layer in how I design, build and iterate faster.",
            False,
            "day-to-day AI template",
        )

    if "ai changed quality" in q or "stakeholder experience" in q or ("not just speed" in q and "quality" in q):
        return (
            "A specific example is using AI to turn rough user input into structured, actionable outputs in my SaaS and automation projects. "
            "The quality improvement was not just speed: users received clearer suggestions, better formatted content and more complete next steps, which reduced the need to rewrite or manually organize the result. "
            "I got there by constraining prompts, adding review steps, using structured outputs, keeping the UI simple and testing whether the generated output was actually useful for the next user action.",
            False,
            "AI quality impact template",
        )

    if "side project" in q and ("ai" in q or "build" in q or "built" in q):
        return (
            "My strongest side projects are AI and full-stack systems such as Goblin Gibber, AIDreamer, GenMint and trading/automation dashboards. "
            "Across these projects I built the frontend, backend APIs, AI integrations and data flows myself, which gave me practical experience turning AI capabilities into usable product features.",
            False,
            "side project template",
        )

    return None


def _structured_form_answer(
    *,
    question: str,
    generated: str,
    job: JobORM,
    prefs: dict,
    rules: dict,
    candidate: dict,
    cv_text: str,
    options: list[str] | None = None,
) -> tuple[str, bool, str]:
    q_raw = question or ""
    q = re.sub(r"\s+", " ", q_raw).strip().lower()
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    yn = _question_has_yes_no_options(opts)
    first, last = _name_parts(candidate)

    if not q or q in {"start typing", "start typing...", "type here", "type here...", "select", "choose", "please select"}:
        return "", True, "placeholder/noise"

    # Pronunciation before pronouns; 'pronounce' contains 'pronoun'.
    if "pronounce" in q or "pronunciation" in q:
        return "Dah-ree-oosh Roh-zah-nek", False, "name pronunciation"

    # Sensitive/voluntary demographics: never use generic technical fallback.
    sensitive_terms = [
        "racial", "ethnic", "ethnicity", "race", "gender identity", "sexual orientation",
        "veteran", "disability", "disabled", "neurodivergent", "religion", "religious",
        "marital", "transgender", "lgbt", "lgbtq",
    ]
    if any(t in q for t in sensitive_terms):
        return _safe_prefer_not_answer(opts)

    # Source questions before LinkedIn profile detection.
    source_terms = ["how did you hear", "how’d you hear", "how'd you hear", "how did you find", "heard about", "hear about", "where did you hear", "source", "job board", "social media"]
    if any(t in q for t in source_terms) and "profile" not in q:
        # Match exact ATS options where available.
        for want in ["LinkedIn", "Job board", "I was reached out to", "Other", "Company careers page", "Careers page"]:
            for opt in opts:
                if want.lower() in opt.lower():
                    return opt, False, "source option"
        return "LinkedIn", False, "source"

    # Candidate identity fields.
    if "preferred first name" in q or "only enter your preferred first name" in q:
        return first, False, "preferred first name"
    if "preferred last name" in q:
        return last, False, "preferred last name"
    if "legal first name" in q or ("first name" in q and "government" in q):
        return first, False, "legal first name from CV"
    if "legal last name" in q or ("last name" in q and "government" in q):
        return last, False, "legal last name from CV"
    if re.fullmatch(r"(?:first\s*)?name|full name", q):
        return candidate.get("fullName") or f"{first} {last}".strip(), False, "candidate name"
    if q in {"first name"}:
        return first, False, "first name"
    if q in {"last name"}:
        return last, False, "last name"
    if q in {"email", "email address"}:
        return candidate.get("email") or "", False, "candidate email"
    if q in {"phone", "phone number", "mobile"}:
        return candidate.get("phone") or "", False, "candidate phone"

    # Location / city / country.
    if q in {"location", "current location", "where are you located"} or "what city/country" in q or "city/country" in q or "work from" in q:
        loc_answer = candidate.get("location") or prefs.get("location") or "Wrexham, United Kingdom"
        if str(loc_answer).strip().lower() in {"uk", "united kingdom"}:
            loc_answer = "Wrexham, United Kingdom"
        return loc_answer, False, "candidate location"

    if "linkedin" in q and ("profile" in q or "url" in q or "link" in q):
        return candidate.get("linkedin") or _manual_check("Add your LinkedIn URL in Settings first."), not bool(candidate.get("linkedin")), "linkedin profile"
    if "github" in q:
        return candidate.get("github") or _manual_check("Optional. Add GitHub URL in Settings if you want to include it."), not bool(candidate.get("github")), "github"
    if q in {"resume", "cv", "upload resume", "upload cv"} or "resume" in q or q == "cv":
        cv_path = _latest_cv_path()
        return (f"Upload this file manually: {cv_path}" if cv_path else _manual_check("Upload your CV manually.")), not bool(cv_path), "cv upload"

    # Pronouns are personal; choose saved value only if explicitly saved.
    if re.search(r"\bpronouns?\b", q):
        saved = str(candidate.get("pronouns") or "").strip()
        if saved:
            return _option_answer(saved, opts), False, "saved pronouns"
        for opt in opts:
            lo = opt.lower()
            if "prefer" in lo or "decline" in lo or "not" in lo:
                return opt, False, "prefer not to say"
        return _manual_check("Choose your pronouns manually. Do not let the bot guess this."), True, "pronouns require manual choice"

    # Years / professional experience.
    if ("3 years" in q or ">3" in q or "more than 3" in q or "over 3" in q) and any(x in q for x in ["web application", "web app", "software", "professionally", "professional"]):
        years = _cv_years_experience(cv_text)
        ans = "Yes" if years >= 3 else "No"
        return _option_answer(ans, opts), years < 3, f"cv years={years}"
    if "years" in q and "experience" in q and any(x in q for x in ["web", "software", "react", "python", "engineer", "developer"]):
        years = _cv_years_experience(cv_text)
        if years:
            return f"{years:g}+ years", False, "years from CV"

    # UK based.
    loc = (candidate.get("location") or prefs.get("location") or "").lower()
    if any(x in q for x in ["currently based in the uk", "based in uk", "based in the uk", "located in the uk", "live in the uk"]):
        ans = "Yes" if ("uk" in loc or "wrexham" in loc or "united kingdom" in loc) else "No"
        return _option_answer(ans, opts), ans == "No", "location"

    # Visa / right-to-work. Do not guess nationality/immigration status.
    if any(x in q for x in ["visa", "sponsor", "sponsorship", "right to work", "authorised", "authorized", "work eligibility", "work permit"]):
        visa = candidate.get("requiresVisaSponsorship")
        right_uk = candidate.get("rightToWorkUK")
        if visa is not None:
            ans = "Yes" if bool(visa) else "No"
            return _option_answer(ans, opts), False, "saved visa sponsorship preference"
        if right_uk is not None and ("uk" in q or "united kingdom" in q):
            ans = "No" if ("require" in q or "need" in q or "sponsor" in q) and bool(right_uk) else ("Yes" if bool(right_uk) else "No")
            return _option_answer(ans, opts), False, "saved UK right-to-work preference"
        return _manual_check("Legal/right-to-work question. Choose the exact option that matches your immigration status; do not guess."), True, "visa/right-to-work manual check"

    # Office / hybrid days.
    if "office" in q or "hybrid" in q or "onsite" in q or "on-site" in q:
        max_days = _max_office_days(rules)
        day_match = re.search(r"(\d+)\s*(?:days?|d)\s*(?:a|per|/)\s*(?:week|wk)", q)
        if day_match:
            required_days = int(day_match.group(1))
            ans = "Yes" if required_days <= max_days else "No"
            return _option_answer(ans, opts), False, f"office days required={required_days}, max={max_days}"
        return f"I am open to remote work and hybrid arrangements with up to {max_days} day(s) per week in office.", False, "hybrid preference"

    # Salary / availability.
    if any(x in q for x in ["salary", "compensation", "expected pay", "rate"]):
        min_perm = prefs.get("minSalaryPermanent") or 0
        min_contract = prefs.get("minSalaryContract") or 0
        if (job.contract_type or "permanent") == "contract" and min_contract:
            return f"My expected day rate is from £{min_contract}/day, depending on scope, contract length and working arrangement.", False, "salary"
        if min_perm:
            return f"My salary expectation is from £{min_perm} per year, depending on the full package, scope and working arrangement.", False, "salary"
        return "I am open to a market-aligned package based on the role scope, seniority and working arrangement.", False, "salary"
    if any(x in q for x in ["notice", "start date", "available to start", "availability"]):
        return "I am available to discuss a suitable start date and can align around the notice period and project timeline.", False, "availability"

    if any(x in q for x in ["privacy", "terms", "consent", "agree", "data processing"]):
        return _manual_check("Review the consent/privacy text yourself before selecting an option."), True, "legal consent manual check"

    template = _open_ended_answer(q_raw, job, candidate, prefs)
    if template:
        return template

    if yn and (not generated or generated.lower().startswith("please review")):
        return _manual_check("This is a yes/no question. Review the job/form context and select Yes or No manually."), True, "yes/no manual check"

    clean_generated = (generated or "").strip()
    if clean_generated and not clean_generated.lower().startswith("please review"):
        # Guardrail: never allow generic tech answer for sensitive questions if missed above.
        if any(t in q for t in ["racial", "ethnic", "gender", "sexual", "veteran", "disability", "disabled"]):
            return _safe_prefer_not_answer(opts)
        return clean_generated, False, "ai generated"

    if any(x in q for x in ["why", "what", "how", "tell", "describe", "experience", "built", "build", "project", "ai", "llm", "machine learning"]):
        return (
            f"I have hands-on experience building full-stack and AI systems using Next.js, TypeScript, Python, FastAPI, Node.js, Supabase and LLM-based workflows. "
            f"For {job.company or 'your team'}, I would focus on practical engineering impact: reliable product features, clear user workflows, maintainable backend services and AI functionality that improves quality, not just speed.",
            False,
            "generic open-ended fallback",
        )

    return "Please review manually and tailor this answer before submitting.", True, "no generated answer"
