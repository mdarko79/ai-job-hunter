"""ATS-friendly CV generation with keyword injection.

Takes the user's CV + a job description, asks the LLM to inject relevant
keywords from the job description into the CV without lying or padding,
then renders to PDF using Playwright.

The HTML template is plain and ATS-safe — no images, no columns, no fancy
fonts that PDF parsers can't read. Single-column, system fonts, semantic
headings.
"""

from __future__ import annotations

import json
import re
import uuid
from html import escape
from pathlib import Path
from typing import Any

from .ai_service import chat_json, chat_text

OUTPUT_DIR = Path("uploads/ats_pdfs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _extract_keywords_heuristic(job_description: str, tech_stack: list[str]) -> list[str]:
    """Pull obvious keywords without LLM."""
    text = f"{job_description} {' '.join(tech_stack or [])}".lower()
    pattern = re.compile(
        r"\b(python|typescript|javascript|react|next\.?js|node\.?js|fastapi|"
        r"django|flask|aws|gcp|azure|docker|kubernetes|k8s|postgres|postgresql|"
        r"mongodb|redis|graphql|rest|kafka|spark|airflow|terraform|ansible|"
        r"rust|go(?:lang)?|java|kotlin|swift|solidity|web3|ethereum|llm|rag|"
        r"openai|anthropic|langchain|pytorch|tensorflow|playwright|selenium|"
        r"tailwind|supabase|firebase|vercel|ci/cd|microservices|agile|scrum|"
        r"figma|api|sql|nosql|tdd|oop|saas|b2b|b2c|machine learning|deep learning|"
        r"data science|nlp|computer vision|fine-?tuning|prompt engineering)\b"
    )
    found = {m.group(0) for m in pattern.finditer(text)}
    # Also pull obvious title-case multi-word tech (e.g. "Apache Kafka")
    multi = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", job_description or "")
    for m in multi:
        if 5 < len(m) < 30:
            found.add(m.lower())
    return sorted(found)[:30]


async def extract_job_keywords(job_description: str, tech_stack: list[str]) -> list[str]:
    """Use LLM to extract the most ATS-relevant keywords from a job description."""
    if not job_description and not tech_stack:
        return []

    fallback = _extract_keywords_heuristic(job_description or "", tech_stack or [])

    try:
        system = (
            "You are an ATS keyword extractor. Pull the 15-25 most important "
            "skills, technologies, and qualifications a candidate must demonstrate "
            "in their CV to pass ATS screening for this role. Prefer concrete "
            "nouns over generic verbs. Avoid fluff like 'team player', 'fast paced'."
        )
        user = f"""Tech stack listed: {', '.join(tech_stack or [])}

Job description:
{(job_description or '')[:4000]}

Return JSON: {{"keywords": ["python", "fastapi", "rag systems", ...]}}"""
        result = await chat_json(system, user)
        kws = result.get("keywords") or []
        cleaned = [str(k).strip() for k in kws if k][:25]
        if len(cleaned) >= 5:
            return cleaned
    except Exception:
        pass
    return fallback


async def inject_keywords_into_cv(
    cv_text: str,
    job: dict[str, Any],
    keywords: list[str],
) -> dict[str, Any]:
    """Have AI rewrite the CV with keywords woven in naturally — no lying."""
    if not cv_text:
        return {"sections": _empty_cv_skeleton(job, keywords), "keywordsUsed": [], "method": "skeleton"}

    if not keywords:
        return {"sections": _parse_cv_to_sections(cv_text), "keywordsUsed": [], "method": "passthrough"}

    system = (
        "You are an ATS optimizer. Rewrite the candidate's CV so it passes ATS "
        "screening for the target role. RULES:\n"
        "1. Never invent skills or experience the candidate doesn't have.\n"
        "2. Where the candidate genuinely has a skill, use the EXACT terminology "
        "from the keywords list (e.g. if they said 'Postgres' and the keyword is "
        "'PostgreSQL', use 'PostgreSQL').\n"
        "3. Reorganize bullet points to lead with relevant achievements.\n"
        "4. Quantify impact where the original CV provides numbers.\n"
        "5. Output structured sections in JSON, no prose."
    )
    user = f"""Target role: {job.get('role','')} at {job.get('company','')}
Target keywords (use those the candidate genuinely has): {', '.join(keywords)}

ORIGINAL CV:
{cv_text[:6000]}

Return JSON of this exact shape:
{{
  "fullName": "...",
  "headline": "1-line professional title aligned to target role",
  "contact": {{"email": "...", "phone": "...", "location": "...", "linkedin": "...", "github": "..."}},
  "summary": "2-3 sentence summary that mirrors the target role language",
  "skills": ["skill1", "skill2", ...],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "dates": "...",
      "bullets": ["impact bullet using keyword X", "impact bullet ...", ...]
    }}
  ],
  "education": [{{"degree": "...", "school": "...", "dates": "..."}}],
  "keywordsUsed": ["which keywords from the list were actually woven in"]
}}"""
    try:
        result = await chat_json(system, user)
        return {
            "sections": result,
            "keywordsUsed": result.get("keywordsUsed") or [],
            "method": "llm",
        }
    except Exception:
        return {"sections": _parse_cv_to_sections(cv_text), "keywordsUsed": [], "method": "passthrough"}


def _empty_cv_skeleton(job: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    return {
        "fullName": "Your Name",
        "headline": job.get("role") or "Software Engineer",
        "contact": {},
        "summary": "Upload a CV first — this is a placeholder.",
        "skills": keywords[:15],
        "experience": [],
        "education": [],
    }


def _parse_cv_to_sections(cv_text: str) -> dict[str, Any]:
    """Crude fallback when LLM is not available — wraps the raw text."""
    return {
        "fullName": "",
        "headline": "",
        "contact": {},
        "summary": cv_text[:500],
        "skills": [],
        "experience": [{"title": "Experience", "company": "", "dates": "", "bullets": [cv_text[500:3000]]}],
        "education": [],
    }


def render_cv_html(sections: dict[str, Any]) -> str:
    """Render sections as ATS-safe HTML (single column, system fonts)."""
    full_name = escape(sections.get("fullName") or "")
    headline = escape(sections.get("headline") or "")
    summary = escape(sections.get("summary") or "")
    contact = sections.get("contact") or {}
    contact_parts = [
        v for k, v in contact.items() if v and isinstance(v, str)
    ]
    contact_line = " · ".join(escape(p) for p in contact_parts)

    skills = sections.get("skills") or []
    skills_html = ", ".join(escape(s) for s in skills if s)

    experience_html = ""
    for exp in sections.get("experience") or []:
        title = escape(exp.get("title") or "")
        company = escape(exp.get("company") or "")
        dates = escape(exp.get("dates") or "")
        bullets = exp.get("bullets") or []
        bullets_html = "".join(f"<li>{escape(b)}</li>" for b in bullets if b)
        experience_html += f"""
        <div class="job">
          <div class="job-head">
            <strong>{title}</strong>
            {('<span class="company"> — ' + company + '</span>') if company else ''}
            <span class="dates">{dates}</span>
          </div>
          {('<ul>' + bullets_html + '</ul>') if bullets_html else ''}
        </div>"""

    education_html = ""
    for edu in sections.get("education") or []:
        degree = escape(edu.get("degree") or "")
        school = escape(edu.get("school") or "")
        dates = escape(edu.get("dates") or "")
        education_html += f"""
        <div class="edu">
          <strong>{degree}</strong>
          {('— ' + school) if school else ''}
          <span class="dates">{dates}</span>
        </div>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{full_name} — CV</title>
<style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  body {{
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #111;
    max-width: 178mm;
    margin: 0;
  }}
  h1 {{ font-size: 22pt; margin: 0 0 2px; letter-spacing: -0.01em; }}
  .headline {{ font-size: 12pt; color: #444; margin-bottom: 6px; }}
  .contact {{ font-size: 9.5pt; color: #555; margin-bottom: 14px; border-bottom: 1px solid #ddd; padding-bottom: 8px; }}
  h2 {{ font-size: 11pt; text-transform: uppercase; letter-spacing: 0.06em;
        margin: 16px 0 6px; color: #222; border-bottom: 1px solid #ccc; padding-bottom: 2px; }}
  .summary {{ margin-bottom: 8px; }}
  .skills {{ margin-bottom: 4px; }}
  .job {{ margin-bottom: 10px; }}
  .job-head {{ margin-bottom: 2px; }}
  .company {{ color: #444; }}
  .dates {{ float: right; color: #666; font-size: 9.5pt; }}
  ul {{ margin: 4px 0 0; padding-left: 18px; }}
  li {{ margin-bottom: 2px; }}
  .edu {{ margin-bottom: 6px; }}
</style>
</head>
<body>
  <h1>{full_name}</h1>
  {('<div class="headline">' + headline + '</div>') if headline else ''}
  {('<div class="contact">' + contact_line + '</div>') if contact_line else ''}

  {('<h2>Summary</h2><div class="summary">' + summary + '</div>') if summary else ''}

  {('<h2>Skills</h2><div class="skills">' + skills_html + '</div>') if skills_html else ''}

  {('<h2>Experience</h2>' + experience_html) if experience_html else ''}

  {('<h2>Education</h2>' + education_html) if education_html else ''}
</body>
</html>"""


async def render_pdf_from_html(html: str, output_path: Path) -> Path:
    """Use Playwright to render HTML to PDF."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        await page.pdf(
            path=str(output_path),
            format="A4",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            print_background=True,
        )
        await browser.close()
    return output_path


async def generate_ats_cv(
    cv_text: str,
    job: dict[str, Any],
) -> dict[str, Any]:
    """Full pipeline: extract keywords -> rewrite CV -> render PDF.

    Returns {pdfPath, pdfUrl, keywords, keywordsUsed, sections}.
    """
    keywords = await extract_job_keywords(
        job.get("description") or "",
        job.get("techStack") or [],
    )
    rewrite = await inject_keywords_into_cv(cv_text or "", job, keywords)
    html = render_cv_html(rewrite["sections"])

    fname = f"cv-{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = OUTPUT_DIR / fname
    try:
        await render_pdf_from_html(html, pdf_path)
        pdf_url = f"/uploads/ats_pdfs/{fname}"
    except Exception as exc:
        # Fallback: save HTML so at least the user has something
        html_path = pdf_path.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        pdf_path = html_path
        pdf_url = f"/uploads/ats_pdfs/{html_path.name}"
        return {
            "pdfPath": str(pdf_path),
            "pdfUrl": pdf_url,
            "keywords": keywords,
            "keywordsUsed": rewrite["keywordsUsed"],
            "sections": rewrite["sections"],
            "error": f"PDF rendering failed (saved as HTML): {exc}",
        }

    return {
        "pdfPath": str(pdf_path),
        "pdfUrl": pdf_url,
        "keywords": keywords,
        "keywordsUsed": rewrite["keywordsUsed"],
        "sections": rewrite["sections"],
    }
