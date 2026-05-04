"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Search,
  Sparkles,
  Send,
  CheckCircle2,
  Gauge,
  Activity,
  RefreshCw,
  AlertCircle,
  Radar,
} from "lucide-react";
import { StatCard } from "@/components/StatCard";
import { JobCard } from "@/components/JobCard";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LogEntry {
  id: string;
  timestamp: string;
  level: string;
  source: string;
  message: string;
}

interface TodayStats {
  appliedToday: number;
  userMaxPerDay: number;
  hardLimit: number;
  effectiveLimit: number;
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [today, setToday] = useState<TodayStats | null>(null);
  const [aiInfo, setAiInfo] = useState<any>(null);
  const [searching, setSearching] = useState(false);
  const [backendOk, setBackendOk] = useState(true);
  const [searchMessage, setSearchMessage] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [jR, lR, tR, hR] = await Promise.all([
        fetch(`${API}/jobs`),
        fetch(`${API}/logs?limit=8`),
        fetch(`${API}/applications/stats/today`),
        fetch(`${API}/health`),
      ]);
      if (!jR.ok || !hR.ok) throw new Error();
      const jobsData = await jR.json();
      setJobs(Array.isArray(jobsData) ? jobsData : []);
      if (lR.ok) setLogs(await lR.json());
      if (tR.ok) setToday(await tR.json());
      if (hR.ok) {
        const h = await hR.json();
        setAiInfo(h.ai);
      }
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    }
  }

  async function runSearch() {
    setSearching(true);
    setSearchMessage(null);
    try {
      const r = await fetch(`${API}/jobs/search`, { method: "POST" });
      const data = await r.json();
      setSearchMessage(`Added ${data.added ?? 0} new jobs`);
      await loadAll();
    } catch {
      setSearchMessage("Search failed");
    } finally {
      setSearching(false);
      setTimeout(() => setSearchMessage(null), 5000);
    }
  }

  useEffect(() => { loadAll(); }, []);

  const highMatch = jobs.filter((j) => j.matchScore >= 80).length;
  const ready = jobs.filter((j) => j.status === "ready").length;
  const avgScore = jobs.length
    ? Math.round(jobs.reduce((s, j) => s + j.matchScore, 0) / jobs.length)
    : 0;
  const recommended = [...jobs]
    .filter((j) => j.matchScore >= 75)
    .sort((a, b) => b.matchScore - a.matchScore)
    .slice(0, 3);

  if (!backendOk) {
    return (
      <div className="rounded-2xl glass p-8 text-center">
        <AlertCircle className="w-10 h-10 text-warn mx-auto mb-3" />
        <h2 className="font-serif text-2xl mb-2">Backend not reachable</h2>
        <p className="text-white/55 text-sm mb-4">
          Make sure FastAPI is running on <code className="text-warn">http://localhost:8000</code>.
        </p>
        <button onClick={loadAll} className="btn-ghost px-4 h-10 inline-flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl glass-strong p-7 lg:p-9 noise">
        <div className="absolute -top-32 -right-20 w-[480px] h-[480px] rounded-full bg-electric/15 blur-[120px] pointer-events-none" />
        <div className="absolute -bottom-32 -left-10 w-[420px] h-[420px] rounded-full bg-accent/12 blur-[120px] pointer-events-none" />

        <div className="relative flex flex-col lg:flex-row lg:items-end gap-6 justify-between">
          <div>
            <div className="label-mono mb-3">
              Today · {new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
            </div>
            <h1 className="font-serif text-4xl lg:text-5xl tracking-tight leading-[1.05]">
              {jobs.length === 0 ? (
                <>Welcome. <span className="italic text-gradient-accent">Click &ldquo;Search jobs&rdquo;</span> to begin.</>
              ) : highMatch > 0 ? (
                <>Your agent has <span className="italic text-gradient-accent">{highMatch} strong {highMatch === 1 ? "match" : "matches"}</span> waiting.</>
              ) : (
                <>{jobs.length} jobs in your pipeline. Click any to review.</>
              )}
            </h1>
            <p className="mt-3 text-white/55 max-w-xl text-[15px]">
              {ready > 0 ? `${ready} ready to send. ` : ""}
              {today ? `${today.appliedToday}/${today.effectiveLimit} applied today. ` : ""}
              {aiInfo?.configured
                ? `AI: ${aiInfo.provider} (${aiInfo.model})`
                : "AI not configured — using heuristics."}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={runSearch}
              disabled={searching}
              className="btn-primary inline-flex items-center gap-2"
            >
              {searching
                ? <><RefreshCw className="w-4 h-4 animate-spin" /> Searching...</>
                : <><Radar className="w-4 h-4" /> Run Job Search</>}
            </button>
            <Link href="/cv" className="btn-ghost inline-flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              Manage CV
            </Link>
          </div>
        </div>

        {searchMessage && (
          <div className="relative mt-4 inline-flex items-center gap-2 text-sm text-accent">
            <CheckCircle2 className="w-4 h-4" />
            {searchMessage}
          </div>
        )}
      </section>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Jobs in pipeline"
          value={String(jobs.length)}
          icon={Search}
          accent="electric"
        />
        <StatCard
          label="High match (≥80%)"
          value={String(highMatch)}
          icon={Sparkles}
          accent="accent"
        />
        <StatCard
          label="Applied today"
          value={today ? `${today.appliedToday}/${today.effectiveLimit}` : "—"}
          icon={Send}
          accent="warn"
        />
        <StatCard
          label="Average match"
          value={`${avgScore}%`}
          icon={Gauge}
          accent="purple"
        />
      </div>

      {/* Recommended jobs */}
      {recommended.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-serif text-2xl">AI recommended</h2>
            <Link href="/jobs" className="text-sm text-white/55 hover:text-white">View all →</Link>
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            {recommended.map((j, i) => <JobCard key={`${j.id}-${i}`} job={j} />)}
          </div>
        </section>
      )}

      {/* Activity feed */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-2xl">Recent activity</h2>
          <Link href="/logs" className="text-sm text-white/55 hover:text-white">View all logs →</Link>
        </div>
        <div className="rounded-2xl glass p-2">
          {logs.length === 0 ? (
            <div className="text-center text-white/40 py-8 text-sm">
              No activity yet. Run a job search to get started.
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {logs.map((log) => (
                <div key={log.id} className="flex items-start gap-3 p-3">
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full mt-2 shrink-0",
                    log.level === "success" && "bg-accent",
                    log.level === "error" && "bg-danger",
                    log.level === "warn" && "bg-warn",
                    log.level === "info" && "bg-electric",
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white/85">{log.message}</div>
                    <div className="text-[10px] font-mono text-white/40 mt-0.5">
                      {new Date(log.timestamp).toLocaleString()} · {log.source}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
