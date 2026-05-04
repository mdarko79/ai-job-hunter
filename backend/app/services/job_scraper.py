"""Multi-source job scraper.

Public sources (no auth required):
  - RemoteOK              public JSON feed
  - Greenhouse boards     boards-api.greenhouse.io/v1/boards/{slug}/jobs
  - Lever boards          api.lever.co/v0/postings/{slug}
  - Ashby boards          api.ashbyhq.com/posting-api/job-board/{slug}
  - Workable boards       apply.workable.com/api/v3/accounts/{slug}/jobs
  - SmartRecruiters       api.smartrecruiters.com/v1/companies/{slug}/postings
  - JustJoin.it           api.justjoin.it/v2/user-panel/offers/embedded   (PL market)
  - NoFluffJobs           nofluffjobs.com/api/posting                     (PL market)

Company lists below are curated for the UK + Europe + AI/Web3/SaaS market.
Edit them freely — they're plain Python lists.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import httpx

UA = {"User-Agent": "ai-job-hunter/0.2 (+https://github.com/local)"}
TIMEOUT = httpx.Timeout(8.0, connect=4.0)


# =============================================================================
# CURATED COMPANY LISTS  ── edit freely
# =============================================================================

# Companies hosted on Greenhouse — boards.greenhouse.io/{slug}
GREENHOUSE_COMPANIES: list[str] = [
    # AI / ML labs and tooling
    "anthropic", "openai", "scaleai", "cohere", "huggingface",
    "perplexityai", "character", "mistralai", "runwayml", "elevenlabs",
    "weightsandbiases", "ai21labs",
    # Dev tooling & infra
    "vercel", "linear", "notion", "figma", "stripe", "plaid", "brex",
    "mercury", "discord", "reddit", "doordash", "airbnb", "cloudflare",
    "datadog", "elastic", "gitlab", "hashicorp", "snowflake", "twilio",
    "zapier", "asana", "atlassian", "dropbox", "instacart", "lyft", "uber",
    "robinhood", "samsara", "pinterest", "squarespace", "automattic",
    "circleci", "sentry", "segment", "amplitude", "mixpanel", "auth0",
    # UK fintech / scale-ups
    "monzo", "wise", "octopusenergy", "cleo", "starling", "gocardless",
    "trustpilot", "deliveroo", "thoughtmachine", "zilch", "tide",
    "checkout", "tractable", "pleo", "qonto", "bunq",
    # Web3 / crypto
    "coinbase", "kraken", "opensea", "chainalysis", "polygontechnology",
    "alchemy", "magiclabs", "consensys", "ledger", "solanafoundation",
    "uniswaplabs", "circle", "ripple", "okx",
    # Other strong tech employers
    "wayfair", "rippling", "gusto", "ramp", "carta", "klaviyo", "duolingo",
    "newrelic", "okta",
]

# Companies hosted on Lever — jobs.lever.co/{slug}
LEVER_COMPANIES: list[str] = [
    # AI
    "replicate", "inflection", "adept-ai", "you", "groq",
    # Big tech / well known
    "netflix", "spotify", "palantir", "patreon", "shopify", "block",
    "twitch", "github", "tiktok",
    # Fintech & EU
    "klarna", "n26", "deepl", "sumup", "adyen", "messagebird", "mollie",
    "raisin", "freetrade", "curve", "bitpanda",
    # Web3
    "binance", "kucoin", "matter-labs", "near", "dydx", "blockdaemon",
    "fireblocks", "celonis",
    # Misc
    "kayak", "yelp", "shippo", "kong", "bolt", "calm", "instabase",
    "humanloop",
]

# Companies on Ashby — jobs.ashbyhq.com/{slug}
ASHBY_COMPANIES: list[str] = [
    "linear", "vanta", "ashby", "posthog", "replit", "modal", "cresta",
    "ramp", "mercury", "watershed", "decagon", "browserbase", "raycast",
    "cursor", "patterns", "metabase", "warp", "tldraw", "supabase",
    "render", "neon", "openpipe", "zed-industries",
    "trychroma", "magicschool", "perplexity", "lambdalabs",
]

# Companies on Workable — apply.workable.com/{slug}
WORKABLE_COMPANIES: list[str] = [
    "intercom", "blueground", "epignosis", "persado", "beat",
    "moonactive", "anyfin", "mews", "kpler", "snyk", "personio",
    "hostaway",
]

# SmartRecruiters companies — slug is the company's CamelCase ID
SMARTRECRUITERS_COMPANIES: list[str] = [
    "Bosch", "Visa", "Square", "Equinox", "Ubisoft", "Publicis",
    "McDonalds",
]


# =============================================================================
# HELPERS
# =============================================================================

_TECH_HINTS = re.compile(
    r"\b(python|typescript|javascript|react|next\.?js|node|fastapi|django|"
    r"flask|aws|gcp|azure|docker|kubernetes|k8s|postgres|mongodb|redis|"
    r"graphql|rest|kafka|spark|airflow|terraform|rust|go(?:lang)?|java|"
    r"kotlin|swift|solidity|web3|ethereum|llm|rag|openai|anthropic|"
    r"langchain|pytorch|tensorflow|playwright|selenium|tailwind|"
    r"supabase|firebase|vercel)\b",
    re.IGNORECASE,
)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").replace("&nbsp;", " ").strip()


def _extract_tech(text: str) -> list[str]:
    if not text:
        return []
    found = {m.group(0).lower() for m in _TECH_HINTS.finditer(text)}
    return sorted(found)[:15]


def _detect_work_mode(location: str, description: str = "") -> str:
    blob = f"{location} {description}".lower()
    if "remote" in blob or "anywhere" in blob:
        return "remote"
    if "hybrid" in blob:
        return "hybrid"
    return "onsite"


async def _safe_get(client: httpx.AsyncClient, url: str) -> dict | list | None:
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# =============================================================================
# ATS SCRAPERS
# =============================================================================

async def fetch_remoteok(query: str = "") -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, "https://remoteok.com/api")
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue
        position = item.get("position") or item.get("title") or ""
        company = item.get("company") or ""
        if query and query.lower() not in (position + " " + company).lower():
            continue
        out.append({
            "id": f"rok-{item.get('id')}",
            "company": company,
            "role": position,
            "location": item.get("location") or "Remote",
            "workMode": "remote",
            "salaryMin": int(item["salary_min"]) if item.get("salary_min") else None,
            "salaryMax": int(item["salary_max"]) if item.get("salary_max") else None,
            "salaryCurrency": "$",
            "contractType": "permanent",
            "description": _strip_html(item.get("description") or "")[:6000],
            "techStack": list(item.get("tags") or [])[:15],
            "source": "RemoteOK",
            "url": item.get("url") or item.get("apply_url"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_greenhouse_board(slug: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(
            client, f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        )
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("jobs", []) or []:
        desc = _strip_html(item.get("content") or "")
        loc = (item.get("location") or {}).get("name") or "Remote"
        out.append({
            "id": f"gh-{slug}-{item.get('id')}",
            "company": slug.replace("-", " ").title(),
            "role": item.get("title", ""),
            "location": loc,
            "workMode": _detect_work_mode(loc, desc),
            "contractType": "permanent",
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("title") or "")),
            "source": "Greenhouse",
            "url": item.get("absolute_url"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_lever_board(slug: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data:
        desc = _strip_html(item.get("descriptionPlain") or item.get("description") or "")
        cats = item.get("categories") or {}
        loc = cats.get("location") or "Remote"
        commitment = cats.get("commitment") or ""
        contract = "contract" if "contract" in commitment.lower() else "permanent"
        out.append({
            "id": f"lv-{slug}-{item.get('id')}",
            "company": slug.replace("-", " ").title(),
            "role": item.get("text", ""),
            "location": loc,
            "workMode": _detect_work_mode(loc, desc),
            "contractType": contract,
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("text") or "")),
            "source": "Lever",
            "url": item.get("hostedUrl"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_ashby_board(slug: str) -> list[dict[str, Any]]:
    """Ashby public job board API."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(
            client,
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
        )
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("jobs", []) or []:
        desc = _strip_html(item.get("descriptionHtml") or item.get("descriptionPlain") or "")
        loc = item.get("locationName") or item.get("location") or "Remote"
        comp = item.get("compensation") or {}
        sal_min = sal_max = None
        if isinstance(comp, dict):
            tiers = comp.get("compensationTierSummary") or ""
            m = re.findall(r"(\d{2,3})[kK]", tiers)
            if len(m) >= 2:
                sal_min, sal_max = int(m[0]) * 1000, int(m[1]) * 1000
        out.append({
            "id": f"ash-{slug}-{item.get('id')}",
            "company": slug.replace("-", " ").title(),
            "role": item.get("title", ""),
            "location": loc,
            "workMode": "remote" if item.get("isRemote") else _detect_work_mode(loc, desc),
            "contractType": "permanent",
            "salaryMin": sal_min,
            "salaryMax": sal_max,
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("title") or "")),
            "source": "Ashby",
            "url": item.get("jobUrl") or item.get("applyUrl"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_workable_board(slug: str) -> list[dict[str, Any]]:
    """Workable public account jobs API."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(
            client, f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
        )
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("results", []) or []:
        desc = _strip_html(item.get("description") or "")
        loc_obj = item.get("location") or {}
        loc = loc_obj.get("city") or loc_obj.get("country") or "Remote"
        if loc_obj.get("region"):
            loc = f"{loc}, {loc_obj['region']}"
        remote_flag = bool(loc_obj.get("workplace") == "remote" or item.get("remote"))
        shortcode = item.get("shortcode")
        out.append({
            "id": f"wkb-{slug}-{shortcode or item.get('id')}",
            "company": slug.replace("-", " ").title(),
            "role": item.get("title", ""),
            "location": loc,
            "workMode": "remote" if remote_flag else _detect_work_mode(loc, desc),
            "contractType": "permanent",
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("title") or "")),
            "source": "Workable",
            "url": f"https://apply.workable.com/{slug}/j/{shortcode}/" if shortcode else None,
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_smartrecruiters_board(slug: str) -> list[dict[str, Any]]:
    """SmartRecruiters public postings API."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(
            client,
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
        )
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("content", []) or []:
        loc_obj = item.get("location") or {}
        loc_parts = [loc_obj.get("city"), loc_obj.get("region"), loc_obj.get("country")]
        loc = ", ".join([p for p in loc_parts if p]) or "Remote"
        remote_flag = bool(loc_obj.get("remote"))
        out.append({
            "id": f"sr-{slug}-{item.get('id')}",
            "company": slug,
            "role": item.get("name", ""),
            "location": loc,
            "workMode": "remote" if remote_flag else _detect_work_mode(loc),
            "contractType": "permanent",
            "description": "",
            "techStack": _extract_tech(item.get("name") or ""),
            "source": "SmartRecruiters",
            "url": (item.get("ref") or {}).get("jobAd"),
            "postedAt": datetime.utcnow(),
        })
    return out


# =============================================================================
# POLISH MARKET
# =============================================================================

async def fetch_justjoinit() -> list[dict[str, Any]]:
    """JustJoin.it embedded offers feed (PL tech market)."""
    url = "https://api.justjoin.it/v2/user-panel/offers/embedded"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, url)
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in (data.get("data") or [])[:200]:
        emp_types = item.get("employmentTypes") or []
        sal_min = sal_max = None
        rate_suffix = None
        contract_type = "permanent"
        if emp_types:
            first = emp_types[0]
            if isinstance(first, dict):
                t = (first.get("type") or "").lower()
                if "b2b" in t or "contract" in t:
                    contract_type = "contract"
                    rate_suffix = "/day"
                from_v = first.get("fromPln") or first.get("from")
                to_v = first.get("toPln") or first.get("to")
                if from_v:
                    sal_min = int(from_v)
                if to_v:
                    sal_max = int(to_v)

        city = item.get("city") or ""
        country = item.get("countryCode") or "PL"
        loc = f"{city}, {country}" if city else country
        remote = bool(item.get("remote") or "remote" in (item.get("workingTime") or "").lower())
        slug = item.get("slug") or item.get("id")
        skills = [s.get("name") for s in (item.get("requiredSkills") or []) if isinstance(s, dict) and s.get("name")]

        out.append({
            "id": f"jji-{slug}",
            "company": item.get("companyName", ""),
            "role": item.get("title", ""),
            "location": loc,
            "workMode": "remote" if remote else "hybrid",
            "salaryMin": sal_min,
            "salaryMax": sal_max,
            "salaryCurrency": "PLN",
            "contractType": contract_type,
            "rateSuffix": rate_suffix,
            "description": "",
            "techStack": skills[:15],
            "source": "JustJoin.it",
            "url": f"https://justjoin.it/offers/{slug}" if slug else None,
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_nofluffjobs() -> list[dict[str, Any]]:
    """NoFluffJobs public posting API (PL market)."""
    url = "https://nofluffjobs.com/api/posting?pageTo=1&pageSize=100"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, url)
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in (data.get("postings") or [])[:200]:
        sal = item.get("salary") or {}
        sal_min = sal.get("from")
        sal_max = sal.get("to")
        currency = sal.get("currency") or "PLN"
        sal_type = (sal.get("type") or "").lower()
        contract_type = "contract" if "b2b" in sal_type else "permanent"
        rate_suffix = "/day" if sal_type == "b2b" and (sal.get("period") or "").lower() == "day" else None

        location_obj = item.get("location") or {}
        places = location_obj.get("places") or []
        city = ""
        if places and isinstance(places[0], dict):
            city = places[0].get("city") or ""
        loc = city or "Poland"
        remote = bool(location_obj.get("fullyRemote"))

        tech: list[str] = []
        for cat in item.get("technology") or []:
            if isinstance(cat, dict) and cat.get("value"):
                tech.append(cat["value"])
        reqs = item.get("requirements")
        if isinstance(reqs, dict):
            for must in reqs.get("musts") or []:
                if isinstance(must, dict) and must.get("value"):
                    tech.append(must["value"])

        company_field = item.get("name")
        if isinstance(company_field, dict):
            company = company_field.get("value") or ""
        else:
            company = company_field or ""

        url_id = item.get("url") or item.get("id")
        out.append({
            "id": f"nfj-{item.get('id')}",
            "company": company,
            "role": item.get("title", ""),
            "location": loc,
            "workMode": "remote" if remote else "hybrid",
            "salaryMin": sal_min,
            "salaryMax": sal_max,
            "salaryCurrency": currency,
            "contractType": contract_type,
            "rateSuffix": rate_suffix,
            "description": "",
            "techStack": list({t for t in tech if t})[:15],
            "source": "NoFluffJobs",
            "url": f"https://nofluffjobs.com/job/{url_id}" if url_id else None,
            "postedAt": datetime.utcnow(),
        })
    return out


# =============================================================================
# ADDITIONAL REMOTE-FOCUSED AGGREGATORS
# =============================================================================

async def fetch_remotive() -> list[dict[str, Any]]:
    """Remotive — public, no auth. Strong remote-only feed."""
    url = "https://remotive.com/api/remote-jobs?limit=200"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, url)
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("jobs", []) or []:
        desc = _strip_html(item.get("description") or "")
        out.append({
            "id": f"rmtv-{item.get('id')}",
            "company": item.get("company_name", ""),
            "role": item.get("title", ""),
            "location": item.get("candidate_required_location") or "Remote",
            "workMode": "remote",
            "salaryMin": None,
            "salaryMax": None,
            "salaryCurrency": "$",
            "contractType": "permanent" if (item.get("job_type") or "").lower() != "contract" else "contract",
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("title") or ""))
                         + [t for t in (item.get("tags") or []) if isinstance(t, str)][:10],
            "source": "Remotive",
            "url": item.get("url"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_working_nomads() -> list[dict[str, Any]]:
    """Working Nomads — public JSON feed, remote-only."""
    url = "https://www.workingnomads.com/api/exposed_jobs/"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA) as client:
        data = await _safe_get(client, url)
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data[:200]:
        desc = _strip_html(item.get("description") or "")
        out.append({
            "id": f"wn-{item.get('id') or hash(item.get('url',''))}",
            "company": item.get("company_name", ""),
            "role": item.get("title", ""),
            "location": item.get("location") or "Remote",
            "workMode": "remote",
            "contractType": "permanent",
            "description": desc[:6000],
            "techStack": _extract_tech(desc + " " + (item.get("title") or "")
                                       + " " + (item.get("category_name") or "")),
            "source": "Working Nomads",
            "url": item.get("url"),
            "postedAt": datetime.utcnow(),
        })
    return out


async def fetch_wellfound_playwright(cookie: str | None = None) -> list[dict[str, Any]]:
    """Wellfound (formerly AngelList Talent) via Playwright.

    Wellfound has NO public API. This requires an authenticated session.
    Set WELLFOUND_COOKIE env var with your `wellfound_session` cookie value.
    Use at your own risk — Wellfound's ToS prohibits automated access.

    Returns [] if no cookie provided. Best-effort scrape, may break if they
    redesign the page.
    """
    if not cookie:
        return []
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    out: list[dict[str, Any]] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            await ctx.add_cookies([{
                "name": "wellfound_session",
                "value": cookie,
                "domain": "wellfound.com",
                "path": "/",
            }])
            page = await ctx.new_page()
            await page.goto("https://wellfound.com/jobs", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            cards = await page.query_selector_all('[data-test="JobSearchCard"]')
            for c in cards[:50]:
                try:
                    role = await (await c.query_selector('a[href*="/jobs/"]')).inner_text()
                    href = await (await c.query_selector('a[href*="/jobs/"]')).get_attribute("href")
                    company_el = await c.query_selector('[data-test="startupNameLink"]')
                    company = await company_el.inner_text() if company_el else ""
                    out.append({
                        "id": f"wf-{href.rsplit('/', 1)[-1] if href else hash(role)}",
                        "company": company,
                        "role": role,
                        "location": "Remote",
                        "workMode": "remote",
                        "contractType": "permanent",
                        "description": "",
                        "techStack": [],
                        "source": "Wellfound",
                        "url": f"https://wellfound.com{href}" if href and href.startswith("/") else href,
                        "postedAt": datetime.utcnow(),
                    })
                except Exception:
                    continue
            await browser.close()
    except Exception:
        return []
    return out


# =============================================================================
# ORCHESTRATOR
# =============================================================================

async def fetch_all(
    query: str | dict | None = "",
    *,
    greenhouse_slugs: list[str] | None = None,
    lever_slugs: list[str] | None = None,
    ashby_slugs: list[str] | None = None,
    workable_slugs: list[str] | None = None,
    smartrecruiters_slugs: list[str] | None = None,
    include_remoteok: bool = True,
    include_polish: bool = True,
    include_remotive: bool = True,
    include_working_nomads: bool = True,
    wellfound_cookie: str | None = None,
    concurrent_limit: int = 25,
) -> list[dict[str, Any]]:
    """Aggregate scrape across all configured sources, in parallel.

    `query` is a substring filter applied client-side after the fetch.
    Pass empty string to skip filtering. Accepts a dict for backward compat.
    """
    if isinstance(query, dict):
        query = ""
    query = (query or "").strip()

    # Default to companies_store (which falls back to hardcoded lists below
    # when the JSON file doesn't exist yet). Explicit kwargs always win.
    if (greenhouse_slugs is None and lever_slugs is None and ashby_slugs is None
            and workable_slugs is None and smartrecruiters_slugs is None):
        try:
            from . import companies_store
            stored = companies_store.get_lists()
            greenhouse_slugs = stored["greenhouse"]
            lever_slugs = stored["lever"]
            ashby_slugs = stored["ashby"]
            workable_slugs = stored["workable"]
            smartrecruiters_slugs = stored["smartrecruiters"]
        except Exception:
            pass

    gh = greenhouse_slugs if greenhouse_slugs is not None else GREENHOUSE_COMPANIES
    lv = lever_slugs if lever_slugs is not None else LEVER_COMPANIES
    ash = ashby_slugs if ashby_slugs is not None else ASHBY_COMPANIES
    wkb = workable_slugs if workable_slugs is not None else WORKABLE_COMPANIES
    sr = smartrecruiters_slugs if smartrecruiters_slugs is not None else SMARTRECRUITERS_COMPANIES

    sem = asyncio.Semaphore(concurrent_limit)

    async def _bound(coro):
        async with sem:
            try:
                return await coro
            except Exception:
                return []

    tasks: list = []
    if include_remoteok:
        tasks.append(_bound(fetch_remoteok(query)))
    if include_remotive:
        tasks.append(_bound(fetch_remotive()))
    if include_working_nomads:
        tasks.append(_bound(fetch_working_nomads()))
    if include_polish:
        tasks.append(_bound(fetch_justjoinit()))
        tasks.append(_bound(fetch_nofluffjobs()))
    if wellfound_cookie:
        tasks.append(_bound(fetch_wellfound_playwright(wellfound_cookie)))
    for slug in gh:
        tasks.append(_bound(fetch_greenhouse_board(slug)))
    for slug in lv:
        tasks.append(_bound(fetch_lever_board(slug)))
    for slug in ash:
        tasks.append(_bound(fetch_ashby_board(slug)))
    for slug in wkb:
        tasks.append(_bound(fetch_workable_board(slug)))
    for slug in sr:
        tasks.append(_bound(fetch_smartrecruiters_board(slug)))

    results = await asyncio.gather(*tasks)

    flat: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for batch in results:
        for job in batch:
            jid = job.get("id")
            if not jid or jid in seen_ids:
                continue
            seen_ids.add(jid)
            if query:
                blob = (
                    f"{job.get('role','')} {job.get('company','')} "
                    f"{' '.join(job.get('techStack') or [])}"
                ).lower()
                if query.lower() not in blob:
                    continue
            flat.append(job)
    return flat
