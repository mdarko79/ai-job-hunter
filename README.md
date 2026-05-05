# AI Job Hunter

AI Job Hunter is a local, human-in-the-loop job search assistant that helps you find relevant roles, score them against your CV and preferences, and prepare high-quality application materials.

The app **does not automatically submit job applications**. It is designed to keep you safe from ATS spam flags by preparing cover letters, form answers and copy-paste application packs, while you review everything and submit manually in your normal browser.

---

## What the app does

AI Job Hunter helps you:

- Upload and parse your CV
- Set target roles, preferred tech stack, locations, work mode and salary expectations
- Search public job sources and company ATS job boards
- Filter out irrelevant roles based on your settings
- Score job matches using AI and deterministic rules
- Generate cover letters tailored to each job
- Extract application form questions where possible
- Generate safe copy-paste answers for application forms
- Track jobs you have manually applied to
- Keep logs of search, scoring and application-pack activity

The current workflow is:

```text
Search Jobs
→ Review matched jobs
→ Open Job
→ Prepare Pack
→ Extract Questions or Paste Questions
→ Copy answers manually
→ Submit yourself in the employer's form
→ Track manual after confirmation
```

---

## Important safety note

Earlier versions experimented with automated form filling and submission. The current recommended workflow avoids automated submission because ATS platforms such as Lever, Greenhouse, Ashby and Workday may flag automated submissions as possible spam.

The app is now designed around a safer workflow:

| Action | Who does it |
|---|---|
| Find jobs | App |
| Score matches | App |
| Generate cover letter | App |
| Extract or answer form questions | App |
| Fill employer form | You |
| Click Submit | You |
| Confirm application was sent | You |
| Track application in dashboard | You |

`submitted` should only mean that you personally submitted the application and confirmed it, for example through a confirmation page or email.

---

## What's inside

```text
ai-job-hunter/
├── frontend/
│   ├── app/              # Dashboard, Jobs, Applications, CV, Rules, Settings, Companies, Logs
│   ├── components/       # Sidebar, TopBar, JobCard, MatchScoreCircle, StatusBadge, StatCard
│   └── lib/              # API wrapper, types, utilities
└── backend/
    ├── app/
    │   ├── routes/       # cv, jobs, applications, match, settings, logs, companies
    │   ├── services/     # ai_service, cv_parser, match_scorer, cover_letter,
    │   │                 # job_scraper, form_question_reader
    │   ├── models.py
    │   ├── schemas.py
    │   ├── database.py
    │   ├── config.py
    │   └── main.py
    ├── uploads/          # local uploads, ignored by Git
    └── requirements.txt
```

---

## Main features

### 1. CV upload and profile extraction

Upload your CV as PDF, DOCX or TXT. The backend extracts the full text and uses it for:

- job matching
- cover letters
- form answers
- application packs

The CV preview page can show the parsed CV text and extracted skills/profile information.

---

### 2. Settings-based job search

You can configure:

- full name
- email
- phone
- location
- target roles
- preferred tech stack
- allowed work modes
- minimum salary
- preferred locations
- AI provider settings

The search and scoring logic uses these settings. For example, if your target roles are Full Stack Developer, AI Engineer and Python Developer, the app focuses on those roles instead of unrelated jobs.

---

### 3. Job search and smart filtering

The backend searches multiple public job sources and ATS APIs, including company career pages where available.

The app filters and scores jobs using:

- target roles
- preferred technologies
- location preferences
- work mode preferences
- salary expectations
- CV relevance
- AI match scoring

This avoids filling the dashboard with unrelated jobs such as hospitality, retail or operations roles when your settings are for software/AI roles.

---

### 4. AI match scoring

Each job receives a match score. The app can use:

- fast heuristic scoring
- AI scoring for top matches
- optional 10-dimension scoring

The goal is to rank jobs by practical fit, not just keyword overlap.

---

### 5. Prepare Pack

For a selected job, **Prepare Pack** creates a copy-paste application pack, including:

- tailored short cover letter
- tailored longer cover letter
- job-specific keywords
- suggested positioning
- company/role-specific notes
- draft-ready application material

This does not submit anything to the employer.

---

### 6. Extract Questions

For supported forms, **Extract Questions** attempts to read visible application form questions and generate answers.

This is useful for questions such as:

- Why this company?
- Why now?
- What is the most impactful thing you have built?
- How did you know it worked?
- Have you used this product?
- How have you used AI in your work?
- Tell us about LLM or AI production experience

If the form is multi-step, behind login, uses captcha or loads questions dynamically, automatic extraction may miss questions.

---

### 7. Paste Questions

For maximum safety and reliability, use **Paste Questions**.

Recommended workflow:

```text
Open Job
→ Copy the employer's form questions manually
→ Paste them into AI Job Hunter
→ Generate answers
→ Copy answers back into the employer form
→ Submit manually
```

This avoids bot detection because the employer form is filled and submitted by you in your normal browser.

---

### 8. Safer form-answer logic

The app has specific handling for common application form fields.

Examples:

| Question type | Example answer behavior |
|---|---|
| First name | Uses your saved first name |
| Last name | Uses your saved last name |
| LinkedIn | Uses your LinkedIn profile |
| Location | Uses your saved location |
| How did you hear about this role? | Uses LinkedIn / company careers page / job board |
| Work authorization | Manual check |
| Visa sponsorship | Manual check |
| Pronouns | Manual check |
| Demographic questions | Manual check / prefer not to say if available |
| Disability/veteran/equal-opportunity questions | Manual check |
| Company-specific factual questions | Manual check |

The app should not guess legal, immigration, demographic or sensitive personal answers.

---

### 9. Track Manual

After you manually submit an application and receive confirmation, click **Track manual**.

This records the application in your dashboard so you can track:

- company
- role
- application date
- status
- cover letter
- application notes

---

## What the app does not do

The current safe version does **not**:

- automatically submit applications
- bypass ATS anti-spam systems
- spoof browser fingerprints
- hide automation signals
- mass-apply without your review
- answer legal or sensitive demographic questions for you
- guarantee that a form was submitted unless you track it after confirmation

This is intentional. The goal is better-quality applications, not high-volume spam.

---

## Prerequisites

- Node.js 20+
- Python 3.10+ or 3.11+
- Git
- Optional: OpenAI API key or another configured AI provider

The app can still run with limited heuristic/template behavior if no AI key is configured.

---

## Installation — Windows / PowerShell

### 1. Clone or open the project

```powershell
cd C:\projekty\ai-job-hunter
```

### 2. Frontend

```powershell
cd C:\projekty\ai-job-hunter\frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open:

```text
http://localhost:3000
```

### 3. Backend

Open a second PowerShell window:

```powershell
cd C:\projekty\ai-job-hunter\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Add your AI API key if you use one.

Run backend:

```powershell
uvicorn app.main:app --reload --port 8000
```

Backend runs at:

```text
http://localhost:8000
```

Swagger docs:

```text
http://localhost:8000/docs
```

---

## Optional Playwright question extraction

The safest workflow is manual paste of questions. However, if you want to use automatic question extraction, Playwright may be used to open and read form pages.

Install browser:

```powershell
cd C:\projekty\ai-job-hunter\backend
.\.venv\Scripts\activate
pip install playwright
python -m playwright install chromium
```

On Windows, if Playwright is used, run backend through the Windows-safe launcher:

```powershell
python run_backend.py
```

Do not use Playwright for auto-submit. Use it only for reading visible questions.

---

## Daily use

1. Upload your CV on the CV page.
2. Configure Settings:
   - target roles
   - tech stack
   - location
   - remote/hybrid preferences
   - salary expectations
3. Click **Search Jobs**.
4. Review matched jobs.
5. Click **Open Job** to inspect the employer page.
6. Click **Prepare Pack** for tailored application material.
7. Use **Extract Questions** or **Paste Questions** to generate form answers.
8. Copy answers manually into the employer form.
9. Submit manually in your normal browser.
10. Click **Track manual** after confirmation.

---

## Recommended settings for remote tech roles

Example:

```text
Target roles:
- Full Stack Developer
- Full Stack Engineer
- AI Engineer
- AI Full Stack Developer
- Python Developer
- React / Next.js Developer
- Web3 Developer

Preferred tech:
- Next.js
- TypeScript
- React
- Python
- FastAPI
- Node.js
- Supabase
- AI Agents
- RAG
- OpenAI API
- Web3
- Solidity

Work mode:
- Remote: on
- Hybrid: on
- Onsite: off or review-only

Max days in office:
- 1 day

Minimum salary:
- Permanent: £40,000+
- Contract: £300/day+
```

---

## Key API endpoints

```text
GET    /jobs                          list scored jobs
POST   /jobs/search                   fetch + score new jobs
POST   /jobs/clear                    clear stored jobs
POST   /jobs/{id}/reject              reject job

GET    /applications                  list tracked applications
GET    /applications/stats/today      today's tracked applications
POST   /applications/prepare-pack/{id} prepare application pack
POST   /applications/extract-form/{id} extract visible form questions
POST   /applications/answer-questions/{id} generate answers from pasted questions
POST   /applications/apply            track manual application

POST   /match                         rescore a job
POST   /match/cover-letter            generate cover letter

POST   /cv/upload                     upload CV
POST   /cv/parse                      parse CV
GET    /cv                            get parsed CV/profile

GET/PUT /settings/prefs               user preferences
GET/PUT /settings/rules               rules and workflow settings
GET    /logs                          recent activity
```

---

## Git and privacy

Never commit:

- `.env`
- API keys
- local SQLite databases
- uploaded CVs
- screenshots
- `.venv`
- `node_modules`
- `.next`

The `.gitignore` should exclude these files.

Before pushing:

```powershell
git status
```

Make sure no private files are staged.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Frontend shows old UI | Stop frontend, delete `.next`, run `npm run dev` again |
| Backend route returns 404 | Check that the latest route file was copied into `backend/app/routes/` |
| Playwright throws `NotImplementedError` on Windows | Run backend with `python run_backend.py` |
| Extract Questions returns nothing | Use Paste Questions manually |
| Answers are too generic | Paste the exact employer questions and regenerate |
| ATS says possible spam | Do not use automated submit; use manual browser submit |
| No confirmation email | Treat as not submitted until confirmed manually |

---

## Project goal

The goal of AI Job Hunter is not to spam hundreds of applications.

The goal is to help you find better-matched jobs faster and prepare stronger, tailored applications while keeping the final submission human-reviewed and safe.
