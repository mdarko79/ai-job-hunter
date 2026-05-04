"""Story Bank — accumulator of STAR+R behavioural stories.

After every application, the LLM mines the candidate's CV + the job's behavioural
themes and produces 1-2 candidate stories. Stories accumulate and after 5+ are
collected, the user can promote favourites to "master stories" — the 5-10
that they'd reuse across interviews.

A STAR+R story has:
  S - Situation
  T - Task
  A - Action
  R - Result
  +R - Reflection (what you learned)

Themes: leadership, conflict, failure, impact, ambiguity, technical-decision,
        cross-functional, mentoring, customer-impact, scaling.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import StoryORM
from .ai_service import chat_json

THEMES = [
    "leadership", "conflict", "failure", "impact", "ambiguity",
    "technical-decision", "cross-functional", "mentoring",
    "customer-impact", "scaling",
]


async def generate_stories_for_application(
    cv_text: str,
    job: dict[str, Any],
    application_id: str,
    max_stories: int = 2,
) -> list[dict[str, Any]]:
    """Mine 1-2 stories from CV that would answer behavioural questions
    likely asked for this role."""
    if not cv_text:
        return []

    system = (
        "You are an interview coach. Mine the candidate's CV for STAR+R stories "
        "(Situation, Task, Action, Result, Reflection) that would answer common "
        "behavioural questions for the target role. Only generate stories grounded "
        "in actual CV content — never fabricate. If the CV doesn't have enough "
        "detail for a strong story on a given theme, skip that theme."
    )
    user = f"""Target role: {job.get('role','')} at {job.get('company','')}
Job description (for behavioural themes hint):
{(job.get('description') or '')[:2000]}

Candidate CV:
{cv_text[:5000]}

Generate up to {max_stories} STAR+R stories. Pick themes from this list that
the role would care about most: {', '.join(THEMES)}.

Return JSON:
{{
  "stories": [
    {{
      "title": "short memorable name (e.g. 'Migrating monolith to microservices under deadline')",
      "theme": "one of the theme keywords",
      "situation": "1-2 sentences, with concrete context (when, where, scale)",
      "task": "1 sentence on what the candidate had to do",
      "action": "2-4 sentences on specific actions THEY took (use 'I' not 'we')",
      "result": "1-2 sentences with quantified impact where possible",
      "reflection": "1 sentence on what they learned or would do differently",
      "answersQuestions": ["Tell me about a time you...", "Describe a situation where..."]
    }}
  ]
}}"""
    try:
        result = await chat_json(system, user)
        raw = result.get("stories") or []
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for s in raw[:max_stories]:
        if not isinstance(s, dict):
            continue
        if not s.get("situation") or not s.get("action"):
            continue
        out.append({
            "id": str(uuid.uuid4()),
            "title": (s.get("title") or "").strip()[:200],
            "theme": (s.get("theme") or "impact").lower().strip(),
            "situation": s.get("situation", ""),
            "task": s.get("task", ""),
            "action": s.get("action", ""),
            "result": s.get("result", ""),
            "reflection": s.get("reflection", ""),
            "answersQuestions": s.get("answersQuestions") or [],
            "sourceApplicationId": application_id,
        })
    return out


async def save_stories(
    session: AsyncSession,
    stories: list[dict[str, Any]],
) -> list[StoryORM]:
    saved: list[StoryORM] = []
    for s in stories:
        # Skip near-duplicates by title
        existing = await session.execute(
            select(StoryORM).where(StoryORM.title == s["title"])
        )
        if existing.scalar_one_or_none():
            continue
        orm = StoryORM(
            id=s["id"],
            title=s["title"],
            theme=s["theme"],
            situation=s["situation"],
            task=s["task"],
            action=s["action"],
            result=s["result"],
            reflection=s["reflection"],
            source_application_id=s.get("sourceApplicationId"),
            answers_questions=s.get("answersQuestions") or [],
        )
        session.add(orm)
        saved.append(orm)
    if saved:
        await session.commit()
    return saved


def story_to_dict(s: StoryORM) -> dict[str, Any]:
    return {
        "id": s.id,
        "title": s.title,
        "theme": s.theme,
        "situation": s.situation,
        "task": s.task,
        "action": s.action,
        "result": s.result,
        "reflection": s.reflection,
        "answersQuestions": s.answers_questions or [],
        "isMaster": s.is_master,
        "timesUsed": s.times_used,
        "sourceApplicationId": s.source_application_id,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
    }
