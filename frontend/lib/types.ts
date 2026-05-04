export type ApplicationMode = "manual" | "semi-auto" | "auto";

export type JobStatus =
  | "new"
  | "draft-ready"
  | "ready"
  | "review-needed"
  | "applied"
  | "auto-applied"
  | "rejected"
  | "interview";

export type WorkMode = "remote" | "hybrid" | "onsite";

export type ContractType = "permanent" | "contract";

export interface Job {
  id: string;
  company: string;
  role: string;
  location: string;
  workMode: WorkMode;
  daysInOffice?: number;
  salaryMin?: number;
  salaryMax?: number;
  salaryCurrency: string;
  contractType: ContractType;
  rateSuffix?: string;
  matchScore: number;
  strongMatches: string[];
  weakPoints: string[];
  recommendation: "apply" | "review" | "reject";
  status: JobStatus;
  mode: ApplicationMode;
  source: string;
  postedAt: string;
  description?: string;
  techStack: string[];
  url?: string;
  dimensions?: Record<string, "A" | "B" | "C" | "D" | "E" | "F"> | null;
  overallGrade?: "A" | "B" | "C" | "D" | "E" | "F" | null;
}

export interface Application {
  id: string;
  jobId: string;
  company: string;
  role: string;
  appliedAt: string;
  mode: ApplicationMode;
  status: "draft-ready" | "review-needed" | "submitted" | "viewed" | "screening" | "interview" | "rejected" | "offer";
  coverLetter?: string;
  screenshotUrl?: string;
  atsPdfUrl?: string | null;
}

export interface AutoApplyRules {
  enabled: boolean;
  maxPerDay: number;
  minMatchScore: number;
  minSalaryPermanent: number;
  minSalaryContract: number;
  workModes: WorkMode[];
  maxDaysInOffice: number;
  requireSalary: boolean;
  requireApprovalLinkedIn: boolean;
  saveScreenshots: boolean;
  blacklistCompanies: string[];
  blacklistKeywords: string[];
  requiredTech: string[];
  // Quality features (opt-in)
  qualityMode: boolean;
  multiDimScoring: boolean;
  minOverallGrade: "A" | "B" | "C" | "D" | "E" | "F";
  autoGenerateATSPDF: boolean;
  autoGenerateStories: boolean;
  enableWellfound: boolean;
  wellfoundCookie: string;
}

export interface Story {
  id: string;
  title: string;
  theme: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  answersQuestions: string[];
  isMaster: boolean;
  timesUsed: number;
  sourceApplicationId?: string | null;
  createdAt: string;
}

export interface UserPrefs {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  cvUploaded: boolean;
  targetRoles: string[];
  preferredTech: string[];
  remote: boolean;
  hybrid: boolean;
  onsite: boolean;
  minSalaryPermanent: number;
  minSalaryContract: number;
  locations: string[];
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "success" | "warn" | "error";
  source: string;
  message: string;
}

export interface DashboardStats {
  jobsToday: number;
  highMatchJobs: number;
  applicationsReady: number;
  appliedToday: number;
  averageMatchScore: number;
  weekTrend: number[];
}
