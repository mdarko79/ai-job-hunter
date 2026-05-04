"""Endpoints for managing the curated company lists used by job_scraper."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..scripts import discover_companies as discovery
from ..services import companies_store

router = APIRouter()


class DiscoverRequest(BaseModel):
    extraCandidates: Optional[list[str]] = None
    mergeWithExisting: bool = True


class ListsUpdate(BaseModel):
    greenhouse: Optional[list[str]] = None
    lever: Optional[list[str]] = None
    ashby: Optional[list[str]] = None
    workable: Optional[list[str]] = None
    smartrecruiters: Optional[list[str]] = None


@router.get("/lists")
async def get_lists():
    return {
        "lists": companies_store.get_lists(),
        "store": companies_store.load(),
    }


@router.put("/lists")
async def put_lists(body: ListsUpdate):
    new_lists: dict[str, list[str]] = {}
    for k in companies_store.ATS_KEYS:
        v = getattr(body, k, None)
        if v is not None:
            new_lists[k] = v
    data = companies_store.update_lists(new_lists)
    return {"ok": True, "store": data}


@router.post("/discover")
async def trigger_discover(body: DiscoverRequest, background: BackgroundTasks):
    state = discovery.get_state()
    if state.get("status") == "running":
        return {
            "ok": False,
            "message": "Discovery already running",
            "state": state,
        }

    async def _run():
        await discovery.run_discovery_task(
            extra_candidates=body.extraCandidates,
            merge_with_existing=body.mergeWithExisting,
        )

    # Use asyncio task instead of BackgroundTasks so it survives the
    # request lifecycle and we can poll its progress.
    asyncio.create_task(_run())
    return {"ok": True, "message": "Discovery started", "state": discovery.get_state()}


@router.get("/discovery-status")
async def discovery_status():
    return discovery.get_state()
