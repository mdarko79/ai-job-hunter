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
  Bot,
  Send,
  Loader2,
  FileText,
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

export function JobCard({ job, onChange }: { job: Job; onChange?: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [coverLetter, setCoverLetter] = useState<string | null>(null);
  const [showCover, setShowCover] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  function flash(type: "ok" | "err", msg: string) {
    setFeedback({ type, msg });
    setTimeout(() => setFeedback(null), 4000);
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

  async function applyJob(mode: "manual" | "semi-auto" | "auto") {
    setBusy("apply");
    try {
      const r = await fetch(`${API}/applications/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId: job.id, mode, answers: {} }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Failed");
      flash("ok", data.message || (mode === "auto" ? "Externally submitted" : mode === "semi-auto" ? "Draft filled" : "Tracked manually"));
      onChange?.();
    } catch (e: any) {
      flash("err", e.message || "Apply failed");
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
              {job.workMode === "hybrid" && job.daysInOffice
                ? ` · ${job.daysInOffice}d office`
                : ""}
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
                <div className="text-[13px] text-white/80 leading-relaxed">
                  {job.strongMatches.join(" · ")}
                </div>
              </div>
              {job.weakPoints && job.weakPoints.length > 0 && (
                <div>
                  <div className="label-mono mb-1.5 flex items-center gap-1.5">
                    <AlertTriangle className="w-3 h-3 text-warn" />
                    Weak points
                  </div>
                  <div className="text-[13px] text-white/80 leading-relaxed">
                    {job.weakPoints.join(" · ")}
                  </div>
                </div>
              )}
            </div>
          )}

          {feedback && (
            <div className={cn(
              "mt-4 rounded-lg px-3 py-2 text-xs",
              feedback.type === "ok"
                ? "bg-accent/10 text-accent border border-accent/20"
                : "bg-danger/10 text-danger border border-danger/20"
            )}>
              {feedback.msg}
            </div>
          )}

          {showCover && coverLetter && (
            <div className="mt-4 rounded-xl bg-white/[0.02] border border-white/[0.06] p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="label-mono text-[10px] flex items-center gap-1.5">
                  <FileText className="w-3 h-3" />
                  Cover letter
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
              onClick={() => applyJob("manual")}
              disabled={busy !== null}
              className="btn-ghost inline-flex items-center gap-1.5"
              title="Only marks this job as manually applied/tracked in your dashboard"
            >
              {busy === "apply" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Track manual
            </button>
            <button
              onClick={() => applyJob("semi-auto")}
              disabled={busy !== null || !job.url}
              className="btn-ghost inline-flex items-center gap-1.5"
              title="Opens the job form, fills your details/CV/cover letter, but does not submit"
            >
              {busy === "apply" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bot className="w-3.5 h-3.5" />}
              Fill Draft
            </button>
            <button
              onClick={() => {
                if (confirm("Submit this application externally now? Playwright will open the job page, fill the form, upload your CV and click Submit only if required fields look complete.")) {
                  applyJob("auto");
                }
              }}
              disabled={busy !== null || !job.url}
              className="btn-primary inline-flex items-center gap-1.5"
              title="Real browser submit. Status becomes submitted only after confirmation is detected."
            >
              {busy === "apply" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Submit Real
            </button>
            <button
              onClick={generateCover}
              disabled={busy !== null}
              className="btn-ghost inline-flex items-center gap-1.5"
            >
              {busy === "cover" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PenLine className="w-3.5 h-3.5" />}
              Cover Letter
            </button>
            <button
              onClick={rescore}
              disabled={busy !== null}
              className="btn-ghost inline-flex items-center gap-1.5"
            >
              {busy === "rescore" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Re-score (10-dim)
            </button>
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener"
                className="btn-ghost inline-flex items-center gap-1.5"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Job
              </a>
            )}
            <button
              onClick={rejectJob}
              disabled={busy !== null}
              className="ml-auto btn-danger inline-flex items-center gap-1.5"
            >
              {busy === "reject" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
