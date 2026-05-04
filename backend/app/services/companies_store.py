"""Loads/saves the curated company lists used by job_scraper.

If `backend/companies.json` exists, lists come from there (so users can refresh
them via discovery). Otherwise falls back to the hardcoded lists shipped with
the scraper module.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

STORE_PATH = Path("companies.json")
ATS_KEYS = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters"]


def _empty_store() -> dict[str, Any]:
    return {
        "updatedAt": None,
        "stats": {k: 0 for k in ATS_KEYS},
        "candidatesTested": 0,
        "lists": {k: [] for k in ATS_KEYS},
    }


def load() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return _empty_store()
    try:
        with STORE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for k in ATS_KEYS:
            data.setdefault("lists", {}).setdefault(k, [])
            data.setdefault("stats", {}).setdefault(k, len(data["lists"][k]))
        return data
    except Exception:
        return _empty_store()


def save(data: dict[str, Any]) -> None:
    data["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    data["stats"] = {k: len(data.get("lists", {}).get(k, [])) for k in ATS_KEYS}
    tmp = STORE_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp.replace(STORE_PATH)


def get_lists() -> dict[str, list[str]]:
    """Return per-ATS slug lists, falling back to hardcoded if store is empty."""
    data = load()
    lists = data.get("lists") or {}
    if any(lists.get(k) for k in ATS_KEYS):
        return {k: list(lists.get(k) or []) for k in ATS_KEYS}

    # Fallback to hardcoded lists from the scraper module
    from . import job_scraper as js
    return {
        "greenhouse": list(js.GREENHOUSE_COMPANIES),
        "lever": list(js.LEVER_COMPANIES),
        "ashby": list(js.ASHBY_COMPANIES),
        "workable": list(js.WORKABLE_COMPANIES),
        "smartrecruiters": list(js.SMARTRECRUITERS_COMPANIES),
    }


def update_lists(new_lists: dict[str, list[str]]) -> dict[str, Any]:
    data = load()
    data.setdefault("lists", {})
    for k in ATS_KEYS:
        if k in new_lists:
            # de-dupe and keep order
            seen: set[str] = set()
            cleaned: list[str] = []
            for s in new_lists[k]:
                s = (s or "").strip()
                if s and s not in seen:
                    seen.add(s)
                    cleaned.append(s)
            data["lists"][k] = cleaned
    save(data)
    return data
