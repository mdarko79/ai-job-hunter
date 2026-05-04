"""Mass-test candidate slugs against all 5 ATS APIs in parallel.

Usage:
    python -m app.scripts.discover_companies               # uses bundled candidates
    python -m app.scripts.discover_companies extra.txt     # plus extra file

Writes results to backend/companies.json. Safe to re-run; incremental — keeps
existing entries that still respond. Honest output: prints how many candidates
were tested and how many succeeded for each ATS.

Discovery is also exposed as a long-running task via POST /companies/discover,
so the UI can trigger it without dropping into a terminal.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Callable

import httpx

from ..services import companies_store

UA = {"User-Agent": "ai-job-hunter-discovery/0.1"}
TIMEOUT = httpx.Timeout(15.0, connect=8.0)
CANDIDATES_FILE = Path(__file__).parent / "candidate_slugs.txt"

# In-process state used by the API endpoint to report progress
_state: dict = {
    "status": "idle",       # idle | running | done | error
    "tested": 0,
    "total": 0,
    "found": {k: 0 for k in companies_store.ATS_KEYS},
    "startedAt": None,
    "finishedAt": None,
    "error": None,
}


def get_state() -> dict:
    return dict(_state)


def _read_candidates(extra_files: list[Path] | None = None) -> list[str]:
    sources = [CANDIDATES_FILE] + list(extra_files or [])
    seen: set[str] = set()
    out: list[str] = []
    for path in sources:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.split("#", 1)[0].strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
    return out


# -- per-ATS probes ---------------------------------------------------------

async def _probe_greenhouse(client: httpx.AsyncClient, slug: str) -> bool:
    try:
        r = await client.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            headers=UA,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, dict) and isinstance(data.get("jobs"), list) and len(data["jobs"]) > 0
    except Exception:
        return False


async def _probe_lever(client: httpx.AsyncClient, slug: str) -> bool:
    try:
        r = await client.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            headers=UA,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, list) and len(data) > 0
    except Exception:
        return False


async def _probe_ashby(client: httpx.AsyncClient, slug: str) -> bool:
    try:
        r = await client.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=UA,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, dict) and isinstance(data.get("jobs"), list) and len(data["jobs"]) > 0
    except Exception:
        return False


async def _probe_workable(client: httpx.AsyncClient, slug: str) -> bool:
    try:
        r = await client.get(
            f"https://apply.workable.com/api/v3/accounts/{slug}/jobs",
            headers=UA,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, dict) and isinstance(data.get("results"), list) and len(data["results"]) > 0
    except Exception:
        return False


async def _probe_smartrecruiters(client: httpx.AsyncClient, slug: str) -> bool:
    try:
        r = await client.get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
            headers=UA,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, dict) and data.get("totalFound", 0) > 0
    except Exception:
        return False


PROBES: dict[str, Callable[[httpx.AsyncClient, str], Awaitable[bool]]] = {
    "greenhouse": _probe_greenhouse,
    "lever": _probe_lever,
    "ashby": _probe_ashby,
    "workable": _probe_workable,
    "smartrecruiters": _probe_smartrecruiters,
}


async def _test_slug(client: httpx.AsyncClient, slug: str) -> dict[str, bool]:
    results = await asyncio.gather(
        *[probe(client, slug) for probe in PROBES.values()],
        return_exceptions=False,
    )
    return dict(zip(PROBES.keys(), results))


async def discover(
    candidates: list[str] | None = None,
    *,
    concurrency: int = 30,
    on_progress: Callable[[int, int, dict[str, int]], None] | None = None,
) -> dict[str, list[str]]:
    """Test candidates against all ATS APIs. Returns per-ATS slug lists."""
    cands = candidates or _read_candidates()
    found: dict[str, list[str]] = {k: [] for k in PROBES}
    counts: dict[str, int] = {k: 0 for k in PROBES}

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async def _one(slug: str) -> tuple[str, dict[str, bool]]:
            async with sem:
                return slug, await _test_slug(client, slug)

        tested = 0
        total = len(cands)
        for coro in asyncio.as_completed([_one(s) for s in cands]):
            slug, hits = await coro
            tested += 1
            for ats, ok in hits.items():
                if ok:
                    found[ats].append(slug)
                    counts[ats] += 1
            if on_progress:
                on_progress(tested, total, dict(counts))

    return found


# -- API-friendly runner ----------------------------------------------------

async def run_discovery_task(
    extra_candidates: list[str] | None = None,
    *,
    merge_with_existing: bool = True,
) -> None:
    """Run discovery, update the in-process state and persist companies.json."""
    from datetime import datetime
    _state.update(
        status="running",
        tested=0,
        total=0,
        found={k: 0 for k in companies_store.ATS_KEYS},
        startedAt=datetime.utcnow().isoformat() + "Z",
        finishedAt=None,
        error=None,
    )
    try:
        candidates = _read_candidates()
        if extra_candidates:
            for s in extra_candidates:
                s = (s or "").strip()
                if s and s not in candidates:
                    candidates.append(s)
        _state["total"] = len(candidates)

        def progress(tested: int, total: int, counts: dict[str, int]) -> None:
            _state["tested"] = tested
            _state["found"] = counts

        found = await discover(candidates, on_progress=progress)

        if merge_with_existing:
            existing = companies_store.get_lists()
            for k, slugs in existing.items():
                for s in slugs:
                    if s not in found[k]:
                        found[k].append(s)

        companies_store.update_lists(found)
        _state["status"] = "done"
        _state["finishedAt"] = datetime.utcnow().isoformat() + "Z"
    except Exception as exc:
        _state["status"] = "error"
        _state["error"] = f"{type(exc).__name__}: {exc}"
        _state["finishedAt"] = datetime.utcnow().isoformat() + "Z"


# -- CLI entry point --------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Discover ATS-hosted companies")
    parser.add_argument("extra", nargs="*", type=Path, help="Extra candidate files")
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--no-merge", action="store_true",
                        help="Don't merge with existing companies.json")
    args = parser.parse_args()

    cands = _read_candidates(args.extra)
    print(f"Loaded {len(cands)} candidates. Testing across 5 ATS APIs ...\n")

    counts: dict[str, int] = {k: 0 for k in PROBES}
    last_print = [0]

    def progress(tested: int, total: int, c: dict[str, int]) -> None:
        counts.update(c)
        if tested - last_print[0] >= 20 or tested == total:
            last_print[0] = tested
            line = " ".join(f"{k}={v}" for k, v in counts.items())
            print(f"\r[{tested:>4}/{total}]  {line}", end="", flush=True)

    found = asyncio.run(discover(cands, concurrency=args.concurrency, on_progress=progress))
    print()

    if not args.no_merge:
        existing = companies_store.get_lists()
        for k, slugs in existing.items():
            for s in slugs:
                if s not in found[k]:
                    found[k].append(s)

    companies_store.update_lists(found)

    print("\nResults written to companies.json:")
    for k in companies_store.ATS_KEYS:
        print(f"  {k:18s} {len(found[k]):4d} companies")
    print(f"\nTotal unique slugs: {sum(len(v) for v in found.values())}")


if __name__ == "__main__":
    _cli()
