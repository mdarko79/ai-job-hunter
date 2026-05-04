# AI Job Hunter

Autonomous job-application agent with a polished dashboard and three application modes
(Manual Review / Semi-Auto / Auto Apply). Frontend is **Next.js 15 + TypeScript + Tailwind**,
backend is **FastAPI + Playwright + OpenAI**, storage is local SQLite.

> **Configurable daily limit:** the auto-apply daily cap is fully **user-selectable
> from 1 to 100** (slider on the *Auto Apply Rules* page). The hard system ceiling
> defaults to 100 and is set via the backend env var `MAX_APPLICATIONS_PER_DAY_HARD_LIMIT`.

---

## What's inside

```
ai-job-hunter/
├── frontend/        # Next.js 15 dashboard (works standalone with mock data)
│   ├── app/         # Dashboard, Jobs, Applications, CV, Rules, Settings, Companies, Logs
│   ├── components/  # Sidebar, TopBar, JobCard, MatchScoreCircle, StatusBadge, StatCard
│   └── lib/         # types, mockData, api wrapper with safe fallback, utils
└── backend/         # FastAPI service
    ├── app/
    │   ├── routes/      # cv, jobs, applications, match, settings, logs
    │   ├── services/    # ai_service, cv_parser, match_scorer, cover_letter,
    │   │                # job_scraper (RemoteOK + Greenhouse + Lever), playwright_apply
    │   ├── models.py    # SQLAlchemy ORM
    │   ├── schemas.py   # Pydantic
    │   ├── database.py
    │   ├── config.py
    │   └── main.py
    ├── uploads/         # screenshots + uploaded CVs
    └── requirements.txt
```

---

## Three application modes

| Mode            | What AI does                                                              | What you do                          |
|-----------------|---------------------------------------------------------------------------|--------------------------------------|
| **Manual**      | Finds + scores job, writes cover letter and form answers                  | Open job, send application yourself  |
| **Semi-Auto**   | Opens the form via Playwright, fills everything, attaches CV & letter     | Review and click *Submit*            |
| **Auto Apply**  | The whole thing — but **only** if the rules pass and daily limit is OK    | Nothing (review later in dashboard)  |

## Quality features (opt-in)

Inspired by [career-ops](https://github.com/santifer/career-ops). All off by default —
flip individual switches on the **Auto Apply Rules** page when you want them.

| Feature                       | What it does                                                          |
|-------------------------------|-----------------------------------------------------------------------|
| **Quality mode** (master)     | Prioritises grade over volume — disables Auto-Apply unless re-enabled |
| **10-dimension A-F scoring**  | Scores roleFit / techFit / compFit / locationFit / cultureFit / growth / learning / companyHealth / appCost — with rationale per dimension |
| **Auto ATS PDF**              | On every apply, AI extracts keywords from the JD and rewrites your CV (without lying) so it passes ATS screening. Saves PDF with the application. |
| **Auto Story Bank**           | After every apply, AI mines your CV for STAR+R behavioural stories. Build up 5-10 master stories that answer most behavioural questions. |
| **Wellfound integration**     | Opt-in Playwright scraper using your session cookie. Risky — their ToS prohibits automation. |

Auto-Apply guardrails are configurable on the **Auto Apply Rules** page:

- Min match score (default 85%)
- Max applications per day — **slider 1 → 100** with presets 5 / 10 / 25 / 100
- Min salary (permanent £ / contract day rate)
- Allowed work modes (remote / hybrid / onsite)
- Max days in office
- Require salary in posting
- Require manual approval for LinkedIn jobs
- Save screenshot before submit
- Blacklist companies / keywords
- Required tech tokens

---

## Prerequisites

- **Node.js 20+** — https://nodejs.org/
- **Python 3.11+** — https://www.python.org/downloads/
- **Git** (optional)
- An **OpenAI API key** (optional — without it, AI features fall back to heuristics)

> The frontend works standalone with built-in mock data — you can see the whole
> dashboard before you set up the backend.

---

## Installation — Windows / PowerShell

### One-time PowerShell setup

If `Activate.ps1` is blocked the first time you create a venv, allow local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 1. Frontend (Next.js)

```powershell
cd ai-job-hunter\frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 — the dashboard loads with mock data immediately.

### 2. Backend (FastAPI)

Open a **second** PowerShell window:

```powershell
cd ai-job-hunter\backend

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt

# Install the Playwright browser (Chromium only — keeps it small)
playwright install chromium

# Configure environment
copy .env.example .env
# Then edit .env in Notepad and paste your OPENAI_API_KEY (optional)
notepad .env

# Run the API
uvicorn app.main:app --reload --port 8000
```

Backend is now at http://localhost:8000 — Swagger UI at http://localhost:8000/docs

The frontend's `.env.local` already points to `http://localhost:8000`, so the moment
the backend is up the dashboard will start using real data.

### Optional: change the hard daily limit

By default the backend allows the slider to go up to **100**. If you want a different
ceiling (e.g. 200), edit `backend\.env`:

```
MAX_APPLICATIONS_PER_DAY_HARD_LIMIT=200
```

The slider clamps automatically based on the value the API returns from
`GET /settings/limits`.

---

## Installation — macOS / Linux

```bash
# Frontend
cd ai-job-hunter/frontend
npm install
cp .env.local.example .env.local
npm run dev

# Backend (new terminal)
cd ai-job-hunter/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

---

## Daily use

1. **Drop your CV** on the *My CV* page (PDF / DOCX / TXT).
2. Hit **Search Jobs** — backend pulls from RemoteOK + Greenhouse + Lever, scores each
   role against your CV, and saves the matches.
3. Open *Matched Jobs*, review the high-match cards, pick a mode per job:
   - **Review** → just opens the original posting
   - **Generate Letter** → AI cover letter you can edit
   - **Auto Fill** → opens Playwright, fills the form, pauses for you to click Submit
4. On the *Auto Apply Rules* page, toggle Auto Apply on, set your daily limit
   (slider, max 100) and tighten the safety rules. Anything that fails a rule is left
   in the *Review needed* column.
5. Watch the *Logs* tab to see what the agent did and why.

---

## Where it searches for jobs

Following the same approach as JobCopilot — scraping **official company career
pages via their ATS APIs**, never LinkedIn/Indeed (which would get you banned).
All sources below are public and require no authentication:

| Source           | Type           | Coverage                                |
|------------------|----------------|-----------------------------------------|
| RemoteOK         | aggregator     | Remote-only, mostly tech/AI/Web3        |
| Remotive         | aggregator     | Curated remote tech jobs                |
| Working Nomads   | aggregator     | Remote jobs, especially European        |
| JustJoin.it      | aggregator     | Polish + Central European tech market   |
| NoFluffJobs      | aggregator     | Polish tech market with salary clarity  |
| Greenhouse       | ATS            | 88 curated companies (Anthropic, Stripe, Monzo, Wise, Coinbase, Vercel, Linear, Notion, Octopus Energy …) |
| Lever            | ATS            | 41 curated companies (Netflix, Spotify, Klarna, N26, Adyen, Binance, DeepL …) |
| Ashby            | ATS            | 27 curated companies (Linear, Vanta, Replit, Mercury, Cursor, Perplexity, Supabase …) |
| Workable         | ATS            | 12 curated EU/UK companies (Snyk, Personio, Mews, Intercom …) |
| SmartRecruiters  | ATS            | 7 large enterprises (Visa, Bosch, Ubisoft …) |
| Wellfound        | opt-in / risky | Requires session cookie (Playwright). Use at your own risk — ToS prohibits automation |

**~175 named companies + 3 aggregators**, all scraped in parallel — but you
can scale this up automatically with **company discovery** (see below).

### Auto-discover thousands of companies

The bundled curated list of 175 names is just the starting point. To find more:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.scripts.discover_companies
```

This tests **694 candidate slugs** (in `app/scripts/candidate_slugs.txt`) against
all 5 ATS APIs in parallel. Takes ~2-5 minutes, writes `backend/companies.json`,
and the scraper will use that file from then on. Realistic outcome:
**500-1500 working companies** depending on which ATS hosts which firms today.

You can also trigger discovery from the **Companies** page in the UI — there's a
"Run discovery" button with live progress (tested X/694, real-time per-ATS counts).

To add more candidates without editing the bundled file, drop a `my_companies.txt`
in the same folder and pass it on the CLI:

```powershell
python -m app.scripts.discover_companies my_companies.txt
```

To manually edit the lists at any time, edit `backend/companies.json` directly,
or PUT to `/companies/lists`.

---

## Tech stack

| Layer        | Tools                                                            |
|--------------|------------------------------------------------------------------|
| Frontend     | Next.js 15, React 18, TypeScript, Tailwind 3, lucide-react       |
| Backend      | FastAPI, Pydantic v2, SQLAlchemy 2 async, aiosqlite              |
| AI           | OpenAI Python SDK (`gpt-4o-mini` by default, configurable)       |
| Automation   | Playwright (Chromium)                                            |
| Job sources  | RemoteOK · Greenhouse · Lever · Ashby · Workable · SmartRecruiters · JustJoin.it · NoFluffJobs |
| Storage      | SQLite + local `uploads/`                                        |

---

## Key API endpoints

```
GET    /jobs                        list scored jobs
POST   /jobs/search                 fetch + score new jobs
POST   /jobs/{id}/reject            mark a job as rejected
GET    /applications                list submitted applications
POST   /applications/apply          {jobId, mode, answers}
GET    /applications/stats/today    today's count vs effective limit
POST   /match                       rescore a job
POST   /match/cover-letter          generate cover letter
POST   /cv/upload                   multipart upload
POST   /cv/parse                    extract profile from CV
GET/PUT /settings/prefs             user preferences
GET/PUT /settings/rules             auto-apply rules (validates maxPerDay ≤ hard limit)
GET    /settings/limits             returns the system hard ceiling
GET    /logs                        recent agent activity
GET    /companies/lists             returns curated company lists (per ATS)
PUT    /companies/lists             manually edit the lists
POST   /companies/discover          start discovery (background task)
GET    /companies/discovery-status  poll discovery progress
```

---

## Safety notes

- **Never** commits your `.env`. The included `.gitignore` already excludes it.
- The backend hard-limits `maxPerDay` on **both** the Pydantic schema (`le=100`)
  and the route handler (`MAX_APPLICATIONS_PER_DAY_HARD_LIMIT`).
- Auto-Apply mode also checks for duplicate applications per `jobId` before submitting.
- Screenshots of every auto-applied form are saved to `backend/uploads/screenshots/`.

---

## Troubleshooting (PowerShell)

| Problem                                            | Fix                                                                                  |
|----------------------------------------------------|--------------------------------------------------------------------------------------|
| `Activate.ps1 cannot be loaded… not digitally signed` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`               |
| `playwright: command not found`                    | Make sure venv is active (`.\.venv\Scripts\Activate.ps1`) before `playwright install`|
| Frontend shows mock data only                      | Backend not running, or `NEXT_PUBLIC_API_URL` doesn't point to the backend           |
| `port 8000 already in use`                         | Run `uvicorn app.main:app --reload --port 8001` and update `.env.local`              |
| `OPENAI_API_KEY` errors                            | Leave it empty — the app falls back to heuristic scoring & template cover letters    |

Have fun and apply responsibly. ✨
