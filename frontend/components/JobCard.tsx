"use client";

import { useState } from "react";
import {
  MapPin,
  Briefcase,
  Wallet,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  X,
  PenLine,
  Send,
  Loader2,
  FileText,
  ClipboardList,
  Copy,
} from "lucide-react";
import type { Job } from "@/lib/types";
import { MatchScoreCircle } from "./MatchScoreCircle";
import { StatusBadge, ModeBadge } from "./StatusBadge";
import { cn, formatSalary, timeAgo } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const workModeLabel: Record<Job["workMode"], string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "Onsite",
};

type ApplicationPack = {
  job: {
    id: string;
    company: string;
    role: string;
    location?: string;
    workMode?: string;
    matchScore?: number;
    url?: string;
    source?: string;
  };
  candidate: {
    fullName?: string;
    email?: string;
    phone?: string;
    location?: string;
    linkedin?: string;
    github?: string;
  };
  coverLetters: {
    short: string;
    long: string;
  };
  keywords: string[];
  suggestedAnswers: Array<{ question: string; answer: string }>;
  links: {
    jobUrl?: string;
    companyDomain?: string;
    aboutSearch?: string;
    careersSearch?: string;
    newsSearch?: string;
  };
  cv: {
    path?: string;
    uploaded: boolean;
    charactersParsed: number;
  };
  checks: {
    duplicateCompanyApplications: number;
    alreadySubmitted: boolean;
    manualSubmitRequired: boolean;
    externalSubmitDisabled: boolean;
  };
  instructions: string[];
};

type FormAnswer = {
  question: string;
  answer: string;
  fieldType?: string;
  required?: boolean;
  options?: string[];
  reviewRequired?: boolean;
  reason?: string;
};

function PackRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="flex items-start justify-between gap-3 border-b border-white/[0.06] py-2 last:border-b-0">
      <div className="text-white/45 text-xs uppercase tracking-wide">{label}</div>
      <div className="text-white/85 text-sm text-right break-all">{value}</div>
    </div>
  );
}

export function JobCard({ job, onChange }: { job: Job; onChange?: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [coverLetter, setCoverLetter] = useState<string | null>(null);
  const [showCover, setShowCover] = useState(false);
  const [pack, setPack] = useState<ApplicationPack | null>(null);
  const [showPack, setShowPack] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [formAnswers, setFormAnswers] = useState<FormAnswer[]>([]);
  const [showFormAnswers, setShowFormAnswers] = useState(false);
  const [pastedQuestions, setPastedQuestions] = useState("");

  function flash(type: "ok" | "err", msg: string) {
    setFeedback({ type, msg });
    setTimeout(() => setFeedback(null), 5000);
  }

  async function copyText(text: string, label = "Copied") {
    try {
      await navigator.clipboard.writeText(text || "");
      flash("ok", label);
    } catch {
      flash("err", "Copy failed");
    }
  }

  async function generateCover() {
    setBusy("cover");
    try {
      const r = await fetch(`${API}/match/cover-letter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId: job.id, tone: "professional" }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Failed");
      setCoverLetter(data.coverLetter || "");
      setShowCover(true);
    } catch (e: any) {
      flash("err", e.message || "Cover letter failed");
    } finally {
      setBusy(null);
    }
  }

  async function preparePack() {
    setBusy("pack");
    try {
      const r = await fetch(`${API}/applications/prepare-pack/${encodeURIComponent(job.id)}`, {
        method: "POST",
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Prepare pack failed");
      setPack(data.pack);
      setShowPack(true);
      flash("ok", data.message || "Application pack prepared");
      // Do not refresh the jobs list here. Refreshing remounts the card and hides the pack panel.
    } catch (e: any) {
      flash("err", e.message || "Prepare pack failed");
    } finally {
      setBusy(null);
    }
  }


  async function extractFormQuestions() {
    setBusy("extract");
    try {
      const r = await fetch(`${API}/applications/extract-form/${encodeURIComponent(job.id)}`, {
        method: "POST",
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error(data.detail || data.error || "Could not extract form questions");
      setFormAnswers(data.answers || []);
      setShowFormAnswers(true);
      flash("ok", data.message || `Extracted ${data.count || 0} question(s)`);
    } catch (e: any) {
      flash("err", e.message || "Extract form questions failed");
    } finally {
      setBusy(null);
    }
  }

  async function answerPastedQuestions() {
    if (!pastedQuestions.trim()) {
      flash("err", "Paste at least one question first");
      return;
    }
    setBusy("paste");
    try {
      const r = await fetch(`${API}/applications/answer-pasted/${encodeURIComponent(job.id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: pastedQuestions }),
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error(data.detail || data.error || "Could not generate answers");
      setFormAnswers(data.answers || []);
      setShowFormAnswers(true);
      flash("ok", data.message || `Generated ${data.count || 0} answer(s)`);
    } catch (e: any) {
      flash("err", e.message || "Generate answers failed");
    } finally {
      setBusy(null);
    }
  }

  async function trackManual() {
    if (!confirm("Only click OK after you have REALLY submitted the application manually on the employer website. Track as submitted?")) return;
    setBusy("track");
    try {
      const r = await fetch(`${API}/applications/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId: job.id, mode: "manual", answers: {} }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Failed");
      flash("ok", data.message || "Tracked manual submission");
      onChange?.();
    } catch (e: any) {
      flash("err", e.message || "Track manual failed");
    } finally {
      setBusy(null);
    }
  }

  async function rejectJob() {
    setBusy("reject");
    try {
      const r = await fetch(`${API}/jobs/${job.id}/reject`, { method: "POST" });
      if (!r.ok) throw new Error();
      flash("ok", "Rejected");
      onChange?.();
    } catch {
      flash("err", "Reject failed");
    } finally {
      setBusy(null);
    }
  }

  async function rescore() {
    setBusy("rescore");
    try {
      const r = await fetch(`${API}/features/dimensional-score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId: job.id }),
      });
      if (!r.ok) throw new Error();
      flash("ok", "Re-scored across 10 dimensions");
      onChange?.();
    } catch {
      flash("err", "Rescore failed");
    } finally {
      setBusy(null);
    }
  }

  const recBg =
    job.recommendation === "apply"
      ? "from-accent/[0.08] to-transparent"
      : job.recommendation === "review"
        ? "from-warn/[0.08] to-transparent"
        : "from-danger/[0.06] to-transparent";

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl glass glass-hover p-5 lg:p-6 transition-all duration-300 group",
        "hover:shadow-glow"
      )}
    >
      <div
        className={cn(
          "absolute inset-0 -z-10 bg-gradient-to-br pointer-events-none opacity-60 group-hover:opacity-100 transition-opacity",
          recBg
        )}
      />

      <div className="flex items-start gap-5">
        <MatchScoreCircle score={job.matchScore} size={64} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-serif text-xl text-white leading-tight">{job.role}</h3>
                <ModeBadge mode={job.mode} />
                {job.overallGrade && (
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-purple/15 text-purple border border-purple/30">
                    Grade {job.overallGrade}
                  </span>
                )}
              </div>
              <div className="mt-1 text-white/60 text-sm flex items-center gap-2 flex-wrap">
                <span className="font-medium text-white/80">{job.company}</span>
                <span className="text-white/20">·</span>
                <span className="font-mono text-[11px] text-white/40">{job.source}</span>
                <span className="text-white/20">·</span>
                <span className="font-mono text-[11px] text-white/40">{timeAgo(job.postedAt)}</span>
              </div>
            </div>
            <StatusBadge status={job.status} />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[13px] text-white/70">
            <span className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-white/40" />
              {job.location}
            </span>
            <span className="flex items-center gap-1.5">
              <Briefcase className="w-3.5 h-3.5 text-white/40" />
              {workModeLabel[job.workMode]}
              {job.workMode === "hybrid" && job.daysInOffice ? ` · ${job.daysInOffice}d office` : ""}
            </span>
            <span className="flex items-center gap-1.5">
              <Wallet className="w-3.5 h-3.5 text-white/40" />
              {formatSalary(job.salaryMin, job.salaryMax, job.salaryCurrency, job.rateSuffix)}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {Array.from(
              new Set(
                (job.techStack || [])
                  .filter(Boolean)
                  .map((t) => String(t).trim())
                  .filter(Boolean)
              )
            )
              .slice(0, 6)
              .map((t, i) => (
                <span
                  key={`${t.toLowerCase()}-${i}`}
                  className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-white/[0.04] border border-white/[0.06] text-white/70"
                >
                  {t}
                </span>
              ))}
          </div>

          {job.strongMatches && job.strongMatches.length > 0 && (
            <div className="mt-4 grid sm:grid-cols-2 gap-3">
              <div>
                <div className="label-mono mb-1.5 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3 h-3 text-accent" />
                  Strong matches
                </div>
                <div className="text-[13px] text-white/80 leading-relaxed">{job.strongMatches.join(" · ")}</div>
              </div>
              {job.weakPoints && job.weakPoints.length > 0 && (
                <div>
                  <div className="label-mono mb-1.5 flex items-center gap-1.5">
                    <AlertTriangle className="w-3 h-3 text-warn" />
                    Weak points
                  </div>
                  <div className="text-[13px] text-white/80 leading-relaxed">{job.weakPoints.join(" · ")}</div>
                </div>
              )}
            </div>
          )}

          {feedback && (
            <div
              className={cn(
                "mt-4 rounded-lg px-3 py-2 text-xs",
                feedback.type === "ok"
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "bg-danger/10 text-danger border border-danger/20"
              )}
            >
              {feedback.msg}
            </div>
          )}

          {showPack && pack && (
            <div className="mt-4 rounded-xl bg-white/[0.02] border border-accent/20 p-4 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="label-mono text-[10px] flex items-center gap-1.5 text-accent">
                    <ClipboardList className="w-3 h-3" />
                    Application Pack — submit manually
                  </div>
                  <p className="text-xs text-white/45 mt-1">
                    Bot prepared the content. Open the job, paste manually, then Track manual after real confirmation.
                  </p>
                </div>
                <button onClick={() => setShowPack(false)} className="text-white/40 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {pack.checks.duplicateCompanyApplications > 0 && (
                <div className="rounded-lg bg-warn/10 border border-warn/20 text-warn px-3 py-2 text-xs">
                  Warning: you already have {pack.checks.duplicateCompanyApplications} application(s) recorded for {job.company}.
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-4">
                <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                  <div className="label-mono text-[10px] mb-2">Candidate fields</div>
                  <PackRow label="Name" value={pack.candidate.fullName} />
                  <PackRow label="Email" value={pack.candidate.email} />
                  <PackRow label="Phone" value={pack.candidate.phone} />
                  <PackRow label="Location" value={pack.candidate.location} />
                  <PackRow label="LinkedIn" value={pack.candidate.linkedin} />
                  <PackRow label="GitHub" value={pack.candidate.github} />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="btn-ghost text-xs" onClick={() => copyText(pack.candidate.fullName || "", "Name copied")}>Copy name</button>
                    <button className="btn-ghost text-xs" onClick={() => copyText(pack.candidate.email || "", "Email copied")}>Copy email</button>
                    <button className="btn-ghost text-xs" onClick={() => copyText(pack.candidate.phone || "", "Phone copied")}>Copy phone</button>
                  </div>
                </div>

                <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                  <div className="label-mono text-[10px] mb-2">Keywords to include</div>
                  <div className="flex flex-wrap gap-1.5">
                    {pack.keywords.map((k, i) => (
                      <span key={`${k}-${i}`} className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-accent/[0.08] border border-accent/20 text-accent">
                        {k}
                      </span>
                    ))}
                  </div>
                  <button className="btn-ghost text-xs mt-3 inline-flex items-center gap-1.5" onClick={() => copyText(pack.keywords.join(", "), "Keywords copied")}>
                    <Copy className="w-3 h-3" /> Copy keywords
                  </button>
                  <div className="mt-3 text-xs text-white/45">
                    CV uploaded: {pack.cv.uploaded ? "Yes" : "No"} · Parsed: {pack.cv.charactersParsed} chars
                  </div>
                </div>
              </div>

              <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="label-mono text-[10px]">Short cover letter</div>
                  <button className="btn-ghost text-xs inline-flex items-center gap-1.5" onClick={() => copyText(pack.coverLetters.short, "Short cover copied")}>
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                </div>
                <pre className="text-xs text-white/80 whitespace-pre-wrap font-sans leading-relaxed max-h-48 overflow-auto">
                  {pack.coverLetters.short}
                </pre>
              </div>

              <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="label-mono text-[10px]">Long cover letter</div>
                  <button className="btn-ghost text-xs inline-flex items-center gap-1.5" onClick={() => copyText(pack.coverLetters.long, "Long cover copied")}>
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                </div>
                <pre className="text-xs text-white/80 whitespace-pre-wrap font-sans leading-relaxed max-h-56 overflow-auto">
                  {pack.coverLetters.long}
                </pre>
              </div>

              <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                <div className="label-mono text-[10px] mb-2">Suggested screening answers</div>
                <div className="space-y-3">
                  {pack.suggestedAnswers.map((qa, i) => (
                    <div key={`${qa.question}-${i}`} className="border-b border-white/[0.06] pb-3 last:border-b-0 last:pb-0">
                      <div className="text-xs text-white/55 mb-1">{qa.question}</div>
                      <div className="text-xs text-white/80 leading-relaxed">{qa.answer}</div>
                      <button className="btn-ghost text-xs mt-2 inline-flex items-center gap-1.5" onClick={() => copyText(qa.answer, "Answer copied")}>
                        <Copy className="w-3 h-3" /> Copy answer
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {job.url && (
                  <a href={job.url} target="_blank" rel="noopener" className="btn-primary inline-flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5" /> Open job to submit manually
                  </a>
                )}
                {pack.links.aboutSearch && (
                  <a href={pack.links.aboutSearch} target="_blank" rel="noopener" className="btn-ghost inline-flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5" /> Company About
                  </a>
                )}
                {pack.links.newsSearch && (
                  <a href={pack.links.newsSearch} target="_blank" rel="noopener" className="btn-ghost inline-flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5" /> Company News
                  </a>
                )}
              </div>
            </div>
          )}

          {showFormAnswers && (
            <div className="mt-4 rounded-xl bg-white/[0.02] border border-purple/20 p-4 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="label-mono text-[10px] flex items-center gap-1.5 text-purple">
                    <FileText className="w-3 h-3" />
                    Application form answers
                  </div>
                  <p className="text-xs text-white/45 mt-1">
                    If automatic extraction finds nothing, paste questions from the employer form below and generate answers safely.
                  </p>
                </div>
                <button onClick={() => setShowFormAnswers(false)} className="text-white/40 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {formAnswers.length === 0 ? (
                <div className="rounded-lg bg-warn/[0.06] border border-warn/20 p-3 text-xs text-white/75 leading-relaxed">
                  No visible custom questions were extracted from this form. Some ATS systems show questions only after login, after clicking the next step, or inside a protected multi-step flow. Paste the questions manually below and generate copy/paste answers.
                </div>
              ) : (
                <div className="space-y-3">
                  {formAnswers.map((qa, i) => (
                    <div key={`${qa.question}-${i}`} className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-xs text-white/70 leading-relaxed">
                            {qa.required ? <span className="text-warn">Required · </span> : null}
                            {qa.reviewRequired ? <span className="text-warn">Manual check · </span> : null}
                            {qa.question}
                          </div>
                          {qa.options && qa.options.length > 0 && (
                            <div className="mt-1 text-[11px] text-white/40">
                              Options: {qa.options.join(" · ")}
                            </div>
                          )}
                          {qa.reason && (
                            <div className="mt-1 text-[11px] text-white/35">
                              Reason: {qa.reason}
                            </div>
                          )}
                        </div>
                        <button className="btn-ghost text-xs inline-flex items-center gap-1.5 shrink-0" onClick={() => copyText(qa.answer, "Answer copied")}>
                          <Copy className="w-3 h-3" /> Copy
                        </button>
                      </div>
                      <pre className={cn("mt-2 text-xs whitespace-pre-wrap font-sans leading-relaxed", qa.reviewRequired ? "text-warn" : "text-white/85")}>
                        {qa.answer}
                      </pre>
                    </div>
                  ))}
                </div>
              )}

              <div className="rounded-lg bg-black/20 border border-white/[0.06] p-3">
                <div className="label-mono text-[10px] mb-2">Paste questions manually</div>
                <textarea
                  value={pastedQuestions}
                  onChange={(e) => setPastedQuestions(e.target.value)}
                  placeholder={"Paste questions here, one per line. Example:\nWhy are you interested in this role?\nDo you require sponsorship?\nWhat is your expected salary?"}
                  className="w-full min-h-28 rounded-lg bg-white/[0.03] border border-white/[0.08] px-3 py-2 text-xs text-white/85 outline-none focus:border-purple/50"
                />
                <button
                  onClick={answerPastedQuestions}
                  disabled={busy !== null || !pastedQuestions.trim()}
                  className="btn-primary mt-3 inline-flex items-center gap-1.5"
                >
                  {busy === "paste" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  Generate answers from pasted questions
                </button>
              </div>
            </div>
          )}


          {showCover && coverLetter && (
            <div className="mt-4 rounded-xl bg-white/[0.02] border border-white/[0.06] p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="label-mono text-[10px] flex items-center gap-1.5">
                  <FileText className="w-3 h-3" /> Cover letter
                </div>
                <button onClick={() => setShowCover(false)} className="text-white/40 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <pre className="text-xs text-white/80 whitespace-pre-wrap font-sans leading-relaxed max-h-72 overflow-auto">
                {coverLetter}
              </pre>
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-2 items-center">
            <button
              onClick={preparePack}
              disabled={busy !== null || !job.url}
              className="btn-primary inline-flex items-center gap-1.5"
              title="Prepare copy/paste application pack. Does not submit externally."
            >
              {busy === "pack" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ClipboardList className="w-3.5 h-3.5" />}
              Prepare Pack
            </button>

            <button
              onClick={extractFormQuestions}
              disabled={busy !== null || !job.url}
              className="btn-ghost inline-flex items-center gap-1.5"
              title="Read employer form questions and generate copy/paste answers. Does not fill or submit anything."
            >
              {busy === "extract" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
              Extract Questions
            </button>
            <button
              onClick={() => setShowFormAnswers(true)}
              disabled={busy !== null}
              className="btn-ghost inline-flex items-center gap-1.5"
              title="Paste application form questions manually and generate answers. Safest mode."
            >
              <ClipboardList className="w-3.5 h-3.5" />
              Paste Questions
            </button>
            <button
              onClick={trackManual}
              disabled={busy !== null}
              className="btn-ghost inline-flex items-center gap-1.5"
              title="Only mark as submitted after you personally submit on the employer site"
            >
              {busy === "track" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Track manual
            </button>
            <button onClick={generateCover} disabled={busy !== null} className="btn-ghost inline-flex items-center gap-1.5">
              {busy === "cover" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PenLine className="w-3.5 h-3.5" />}
              Cover Letter
            </button>
            <button onClick={rescore} disabled={busy !== null} className="btn-ghost inline-flex items-center gap-1.5">
              {busy === "rescore" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Re-score (10-dim)
            </button>
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener" className="btn-ghost inline-flex items-center gap-1.5">
                <ExternalLink className="w-3.5 h-3.5" /> Open Job
              </a>
            )}
            <button onClick={rejectJob} disabled={busy !== null} className="ml-auto btn-danger inline-flex items-center gap-1.5">
              {busy === "reject" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
