import type { Job, Application, AutoApplyRules, UserPrefs, LogEntry, DashboardStats } from "./types";

export const mockStats: DashboardStats = {
  jobsToday: 42,
  highMatchJobs: 11,
  applicationsReady: 7,
  appliedToday: 3,
  averageMatchScore: 82,
  weekTrend: [12, 18, 25, 22, 31, 38, 42]
};

export const mockJobs: Job[] = [
  {
    id: "j-001",
    company: "Fireflai",
    role: "Full Stack Developer",
    location: "Manchester, UK",
    workMode: "hybrid",
    daysInOffice: 1,
    salaryMin: 350,
    salaryMax: 400,
    salaryCurrency: "£",
    contractType: "contract",
    rateSuffix: "/day",
    matchScore: 91,
    strongMatches: ["Next.js", "Node.js", "TypeScript", "AI APIs", "SaaS experience"],
    weakPoints: ["Some Azure experience preferred"],
    recommendation: "apply",
    status: "ready",
    mode: "semi-auto",
    source: "LinkedIn",
    postedAt: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    techStack: ["Next.js", "Node", "TypeScript", "Python", "OpenAI"],
    description:
      "We're building an AI-first product platform and looking for a hands-on full-stack developer who can ship across the stack."
  },
  {
    id: "j-002",
    company: "Avantra",
    role: "AI Engineer",
    location: "UK Remote",
    workMode: "remote",
    salaryMin: 55000,
    salaryMax: 70000,
    salaryCurrency: "£",
    contractType: "permanent",
    matchScore: 88,
    strongMatches: ["Python", "FastAPI", "LLM", "RAG", "OpenAI"],
    weakPoints: ["More enterprise experience would help"],
    recommendation: "apply",
    status: "draft-ready",
    mode: "manual",
    source: "Greenhouse",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    techStack: ["Python", "FastAPI", "LangChain", "Postgres"]
  },
  {
    id: "j-003",
    company: "MFK Labs",
    role: "Python Developer",
    location: "Remote",
    workMode: "remote",
    salaryMin: 55000,
    salaryMax: 65000,
    salaryCurrency: "£",
    contractType: "permanent",
    matchScore: 89,
    strongMatches: ["Python", "FastAPI", "PostgreSQL", "Docker"],
    weakPoints: [],
    recommendation: "apply",
    status: "auto-applied",
    mode: "auto",
    source: "RemoteOK",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
    techStack: ["Python", "FastAPI", "Postgres", "Docker"]
  },
  {
    id: "j-004",
    company: "Northwind Studios",
    role: "Senior React Engineer",
    location: "London, UK",
    workMode: "hybrid",
    daysInOffice: 3,
    salaryMin: 70000,
    salaryMax: 90000,
    salaryCurrency: "£",
    contractType: "permanent",
    matchScore: 67,
    strongMatches: ["React", "TypeScript"],
    weakPoints: ["3 days in-office", "Heavy Redux usage", "No AI work"],
    recommendation: "reject",
    status: "review-needed",
    mode: "manual",
    source: "Lever",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
    techStack: ["React", "Redux", "TypeScript"]
  },
  {
    id: "j-005",
    company: "Lumen AI",
    role: "Full Stack AI Engineer",
    location: "Europe Remote",
    workMode: "remote",
    salaryMin: 65000,
    salaryMax: 85000,
    salaryCurrency: "£",
    contractType: "permanent",
    matchScore: 94,
    strongMatches: ["Next.js", "TypeScript", "Python", "OpenAI", "RAG", "Supabase"],
    weakPoints: [],
    recommendation: "apply",
    status: "ready",
    mode: "semi-auto",
    source: "Workable",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
    techStack: ["Next.js", "TypeScript", "Python", "OpenAI", "Supabase"]
  },
  {
    id: "j-006",
    company: "Chainframe",
    role: "Web3 / Solidity Engineer",
    location: "Remote EU",
    workMode: "remote",
    salaryMin: 400,
    salaryMax: 500,
    salaryCurrency: "£",
    contractType: "contract",
    rateSuffix: "/day",
    matchScore: 81,
    strongMatches: ["Solidity", "TypeScript", "Next.js"],
    weakPoints: ["Less DeFi experience"],
    recommendation: "apply",
    status: "draft-ready",
    mode: "manual",
    source: "Web3 Careers",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString(),
    techStack: ["Solidity", "Next.js", "Hardhat", "ethers.js"]
  },
  {
    id: "j-007",
    company: "Pingboard",
    role: "Frontend Engineer",
    location: "London (onsite)",
    workMode: "onsite",
    daysInOffice: 5,
    salaryMin: 60000,
    salaryMax: 75000,
    salaryCurrency: "£",
    contractType: "permanent",
    matchScore: 54,
    strongMatches: ["React", "TypeScript"],
    weakPoints: ["Onsite only", "No AI work"],
    recommendation: "reject",
    status: "rejected",
    mode: "manual",
    source: "LinkedIn",
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 18).toISOString(),
    techStack: ["React", "TypeScript", "GraphQL"]
  }
];

export const mockApplications: Application[] = [
  {
    id: "a-001",
    jobId: "j-003",
    company: "MFK Labs",
    role: "Python Developer",
    appliedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    mode: "auto",
    status: "submitted"
  },
  {
    id: "a-002",
    jobId: "j-008",
    company: "Trailbase",
    role: "Senior Engineer",
    appliedAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    mode: "semi-auto",
    status: "viewed"
  },
  {
    id: "a-003",
    jobId: "j-009",
    company: "Cobalt Systems",
    role: "AI Full Stack Developer",
    appliedAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
    mode: "manual",
    status: "screening"
  },
  {
    id: "a-004",
    jobId: "j-010",
    company: "Helio.dev",
    role: "Next.js Engineer",
    appliedAt: new Date(Date.now() - 1000 * 60 * 60 * 96).toISOString(),
    mode: "semi-auto",
    status: "interview"
  }
];

export const defaultRules: AutoApplyRules = {
  enabled: false,
  maxPerDay: 10,
  minMatchScore: 85,
  minSalaryPermanent: 55000,
  minSalaryContract: 350,
  workModes: ["remote", "hybrid"],
  maxDaysInOffice: 1,
  requireSalary: true,
  requireApprovalLinkedIn: true,
  saveScreenshots: true,
  blacklistCompanies: [],
  blacklistKeywords: ["unpaid", "intern", "internship"],
  requiredTech: [],
  // Quality features — all off by default
  qualityMode: false,
  multiDimScoring: false,
  minOverallGrade: "B",
  autoGenerateATSPDF: false,
  autoGenerateStories: false,
  enableWellfound: false,
  wellfoundCookie: "",
};

export const defaultPrefs: UserPrefs = {
  fullName: "",
  email: "",
  phone: "",
  location: "Manchester, UK",
  cvUploaded: false,
  targetRoles: [
    "Full Stack Developer",
    "Full Stack Engineer",
    "AI Engineer",
    "AI Full Stack Developer",
    "Python Developer",
    "React / Next.js Developer",
    "Web3 Developer"
  ],
  preferredTech: [
    "Next.js",
    "TypeScript",
    "React",
    "Python",
    "FastAPI",
    "Node.js",
    "Supabase",
    "AI Agents",
    "RAG",
    "OpenAI API",
    "Web3",
    "Solidity"
  ],
  remote: true,
  hybrid: true,
  onsite: false,
  minSalaryPermanent: 55000,
  minSalaryContract: 350,
  locations: ["UK Remote", "Europe Remote", "Manchester (max 1 day office)"]
};

export const mockLogs: LogEntry[] = [
  {
    id: "l-001",
    timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    level: "success",
    source: "auto-apply",
    message: "Applied to MFK Labs — Python Developer (match 89%)"
  },
  {
    id: "l-002",
    timestamp: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
    level: "info",
    source: "scraper",
    message: "Scraped 42 jobs from LinkedIn, RemoteOK, Greenhouse, Lever, Workable"
  },
  {
    id: "l-003",
    timestamp: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
    level: "info",
    source: "matcher",
    message: "Scored 42 jobs — 11 above 85% threshold"
  },
  {
    id: "l-004",
    timestamp: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
    level: "warn",
    source: "auto-apply",
    message: "Skipped Northwind Studios — fails work-mode rule (3 days office)"
  },
  {
    id: "l-005",
    timestamp: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    level: "success",
    source: "ai",
    message: "Generated cover letter for Avantra — AI Engineer"
  },
  {
    id: "l-006",
    timestamp: new Date(Date.now() - 1000 * 60 * 41).toISOString(),
    level: "error",
    source: "playwright",
    message: "CAPTCHA detected on Pingboard — flagged for manual review"
  }
];
