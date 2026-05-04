from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

ApplicationMode = Literal["manual", "semi-auto", "auto"]
JobStatus = Literal[
    "new", "draft-ready", "ready", "review-needed", "applied",
    "auto-applied", "rejected", "interview"
]
WorkMode = Literal["remote", "hybrid", "onsite"]
ContractType = Literal["permanent", "contract"]


class JobIn(BaseModel):
    id: str
    company: str
    role: str
    location: str = ""
    workMode: WorkMode = "remote"
    daysInOffice: Optional[int] = None
    salaryMin: Optional[int] = None
    salaryMax: Optional[int] = None
    salaryCurrency: str = "£"
    contractType: ContractType = "permanent"
    rateSuffix: Optional[str] = None
    description: Optional[str] = None
    techStack: list[str] = []
    source: str = ""
    url: Optional[str] = None


class JobOut(JobIn):
    matchScore: int = 0
    strongMatches: list[str] = []
    weakPoints: list[str] = []
    recommendation: Literal["apply", "review", "reject"] = "review"
    status: JobStatus = "new"
    mode: ApplicationMode = "manual"
    postedAt: datetime


class ApplicationOut(BaseModel):
    id: str
    jobId: str
    company: str
    role: str
    appliedAt: datetime
    mode: ApplicationMode
    status: Literal["submitted", "viewed", "screening", "interview", "rejected", "offer"]
    coverLetter: Optional[str] = None
    screenshotUrl: Optional[str] = None


class AutoApplyRules(BaseModel):
    enabled: bool = False
    maxPerDay: int = Field(default=10, ge=1, le=100)
    minMatchScore: int = Field(default=85, ge=0, le=100)
    minSalaryPermanent: int = 55000
    minSalaryContract: int = 350
    workModes: list[WorkMode] = ["remote", "hybrid"]
    maxDaysInOffice: int = 1
    requireSalary: bool = True
    requireApprovalLinkedIn: bool = True
    saveScreenshots: bool = True
    blacklistCompanies: list[str] = []
    blacklistKeywords: list[str] = []
    requiredTech: list[str] = []
    # ---- Quality features (opt-in, "career-ops style") ----
    qualityMode: bool = False              # Master toggle for quality-first behaviour
    multiDimScoring: bool = False          # Use 10-dimension A-F scoring
    minOverallGrade: str = "B"             # Filter out anything below this when qualityMode on
    autoGenerateATSPDF: bool = False       # Generate ATS-optimized PDF on each apply
    autoGenerateStories: bool = False      # Mine STAR+R stories after each application
    enableWellfound: bool = False          # Try Wellfound via Playwright (needs cookie)
    wellfoundCookie: str = ""              # wellfound_session cookie value


class UserPrefs(BaseModel):
    fullName: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    cvUploaded: bool = False
    targetRoles: list[str] = []
    preferredTech: list[str] = []
    remote: bool = True
    hybrid: bool = True
    onsite: bool = False
    minSalaryPermanent: int = 55000
    minSalaryContract: int = 350
    locations: list[str] = []


class MatchRequest(BaseModel):
    jobId: str
    cvText: Optional[str] = None


class CoverLetterRequest(BaseModel):
    jobId: str
    tone: Literal["professional", "warm", "concise"] = "professional"


class ApplyRequest(BaseModel):
    jobId: str
    mode: ApplicationMode = "semi-auto"
    answers: dict[str, str] = {}


class LogOut(BaseModel):
    id: str
    timestamp: datetime
    level: Literal["info", "success", "warn", "error"]
    source: str
    message: str
