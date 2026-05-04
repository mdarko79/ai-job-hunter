"use client";

import { useEffect, useState } from "react";
import { Filter, Search, RefreshCw, Radar, AlertCircle, CheckCircle2, Trash2, Send } from "lucide-react";
import { JobCard } from "@/components/JobCard";
import { mockJobs } from "@/lib/mockData";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const filters = [
  { id: "all", label: "All" },
  { id: "high", label: "High match (≥80%)" },
  { id: "ready", label: "Ready" },
  { id: "applied", label: "Applied" },
  { id: "rejected", label: "Rejected" },
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [autoApplying, setAutoApplying] = useState(false);
  const [usingMock, setUsingMock] = useState(false);
  const [searchMessage, setSearchMessage] = useState<string | null>(null);

  async function loadJobs() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/jobs`);
      if (!r.ok) throw new Error();
      const data = await r.json();
      if (Array.isArray(data) && data.length > 0) {
        setJobs(data);
        setUsingMock(false);
      } else {
        // Backend reachable but empty — show empty, not mock
        setJobs([]);
        setUsingMock(false);
      }
    } catch {
      // Backend offline — show mock so user sees something
      setJobs(mockJobs as Job[]);
      setUsingMock(true);
    } finally {
      setLoading(false);
    }
  }

  async function runSearch() {
    setSearching(true);
    setSearchMessage(null);
    try {
      const r = await fetch(`${API}/jobs/search`, { method: "POST" });
      if (!r.ok) throw new Error("Search failed");
      const data = await r.json();
      setSearchMessage(`✓ Added ${data.added ?? 0} new jobs`);
      await loadJobs();
    } catch {
      setSearchMessage("✗ Search failed — is the backend running?");
    } finally {
      setSearching(false);
      setTimeout(() => setSearchMessage(null), 5000);
    }
  }

  async function runAutoApply() {
    const highMatches = jobs.filter((j) =>
      j.matchScore >= 75 &&
      j.status !== "applied" &&
      j.status !== "auto-applied" &&
      j.status !== "rejected"
    ).length;

    if (!confirm(`Run Auto Apply now?\n\nThe backend will only submit jobs that pass every rule in Rules. Current visible high-match candidates: ${highMatches}.`)) {
      return;
    }

    setAutoApplying(true);
    setSearchMessage(null);
    try {
      const r = await fetch(`${API}/applications/auto-run`, { method: "POST" });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Auto Apply failed");

      const applied = data.applied ?? 0;
      const failed = data.failed ?? 0;
      const skipped = data.skipped ?? 0;
      const remaining = data.remainingToday ?? 0;
      setSearchMessage(`✓ Auto Apply finished: ${applied} submitted, ${failed} failed, ${skipped} skipped, ${remaining} left today`);
      await loadJobs();
    } catch (e: any) {
      setSearchMessage(`✗ ${e.message || "Auto Apply failed — check backend logs"}`);
    } finally {
      setAutoApplying(false);
      setTimeout(() => setSearchMessage(null), 8000);
    }
  }

  useEffect(() => { loadJobs(); }, []);

  const filtered = jobs.filter((j) => {
    if (active === "high" && j.matchScore < 80) return false;
    if (active === "ready" && j.status !== "ready") return false;
    if (active === "applied" && j.status !== "applied" && j.status !== "auto-applied") return false;
    if (active === "rejected" && j.status !== "rejected") return false;
    if (query) {
      const q = query.toLowerCase();
      const blob = `${j.role} ${j.company} ${(j.techStack || []).join(" ")}`.toLowerCase();
      if (!blob.includes(q)) return false;
    }
    return true;
  });

  function countFor(id: string): number {
    if (id === "all") return jobs.length;
    if (id === "high") return jobs.filter((j) => j.matchScore >= 80).length;
    if (id === "ready") return jobs.filter((j) => j.status === "ready").length;
    if (id === "applied") return jobs.filter((j) => j.status === "applied" || j.status === "auto-applied").length;
    if (id === "rejected") return jobs.filter((j) => j.status === "rejected").length;
    return 0;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="label-mono mb-2">Job Search</div>
          <h1 className="font-serif text-4xl tracking-tight">Available roles</h1>
          <p className="text-white/55 mt-1 text-[15px]">
            Pulls from RemoteOK · JustJoin.it · NoFluffJobs · Greenhouse · Lever · Ashby · Workable · SmartRecruiters · Remotive · Working Nomads.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              if (!confirm("Clear all jobs except applied ones?")) return;
              try {
                const r = await fetch(`${API}/jobs/clear?keep_applied=true`, { method: "POST" });
                if (r.ok) {
                  const d = await r.json();
                  setSearchMessage(`✓ Cleared ${d.deleted} jobs`);
                  await loadJobs();
                  setTimeout(() => setSearchMessage(null), 5000);
                }
              } catch {}
            }}
            className="btn-ghost px-4 h-11 inline-flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
          <button
            onClick={runAutoApply}
            disabled={autoApplying || searching || usingMock}
            className="btn-ghost px-4 h-11 inline-flex items-center gap-2 border-accent/30 text-accent hover:bg-accent/10 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Submit applications only for jobs that pass every Auto Apply rule"
          >
            {autoApplying ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> Auto applying...</>
            ) : (
              <><Send className="w-4 h-4" /> Run Auto Apply</>
            )}
          </button>
          <button
            onClick={runSearch}
            disabled={searching}
            className="btn-primary px-5 h-11 inline-flex items-center gap-2"
          >
            {searching ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> Searching...</>
            ) : (
              <><Radar className="w-4 h-4" /> Search jobs</>
            )}
          </button>
        </div>
      </div>

      {searchMessage && (
        <div className={cn(
          "rounded-xl p-3 text-sm flex items-center gap-2",
          searchMessage.startsWith("✓")
            ? "bg-accent/10 border border-accent/20 text-accent"
            : "bg-danger/10 border border-danger/20 text-danger"
        )}>
          {searchMessage.startsWith("✓")
            ? <CheckCircle2 className="w-4 h-4" />
            : <AlertCircle className="w-4 h-4" />}
          {searchMessage.replace(/^[✓✗]\s*/, "")}
        </div>
      )}

      {usingMock && (
        <div className="rounded-xl bg-warn/10 border border-warn/20 text-warn p-3 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Backend not reachable — showing mock data. Start FastAPI on port 8000.
        </div>
      )}

      {/* Search & filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[260px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search role, company, tech…"
            className="w-full bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-xl h-11 pl-10 pr-4 text-sm"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {filters.map((f) => {
            const count = countFor(f.id);
            return (
              <button
                key={f.id}
                onClick={() => setActive(f.id)}
                className={cn(
                  "px-3 h-11 rounded-xl text-sm border inline-flex items-center gap-1.5 transition",
                  active === f.id
                    ? "bg-white/10 border-white/20"
                    : "bg-white/[0.02] border-white/5 text-white/55 hover:border-white/10"
                )}
              >
                {f.label}
                <span className="font-mono text-xs text-white/40">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {loading && jobs.length === 0 ? (
        <div className="text-center text-white/40 py-12">Loading jobs...</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl glass p-10 text-center">
          <Search className="w-10 h-10 mx-auto text-white/30 mb-3" />
          <h3 className="font-serif text-xl mb-2">
            {jobs.length === 0 ? "No jobs yet" : "No jobs match your filters"}
          </h3>
          <p className="text-white/50 text-sm max-w-md mx-auto">
            {jobs.length === 0
              ? "Click \"Search jobs\" above to pull fresh listings from 10+ sources. Takes 10-30 seconds."
              : "Try clearing your search or switching tabs."}
          </p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4">
          {filtered.map((j, i) => <JobCard key={`${j.id}-${i}`} job={j} onChange={loadJobs} />)}
        </div>
      )}
    </div>
  );
}
