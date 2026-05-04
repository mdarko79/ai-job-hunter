"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Send, ExternalLink, FileText, Image as ImageIcon, AlertCircle, RefreshCw } from "lucide-react";
import { StatusBadge, ModeBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import type { Application } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendOk, setBackendOk] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/applications`);
      if (!r.ok) throw new Error();
      const data = await r.json();
      setApps(Array.isArray(data) ? data : []);
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const filtered = apps.filter((a) => filter === "all" ? true : a.status === filter);
  const counts = {
    all: apps.length,
    submitted: apps.filter((a) => a.status === "submitted").length,
    screening: apps.filter((a) => a.status === "screening").length,
    interview: apps.filter((a) => a.status === "interview").length,
    rejected: apps.filter((a) => a.status === "rejected").length,
    offer: apps.filter((a) => a.status === "offer").length,
  };

  if (!backendOk) {
    return (
      <div className="rounded-2xl glass p-8 text-center">
        <AlertCircle className="w-10 h-10 text-warn mx-auto mb-3" />
        <h2 className="font-serif text-2xl mb-2">Backend not reachable</h2>
        <p className="text-white/55 text-sm mb-4">
          Make sure FastAPI is running on <code className="text-warn">http://localhost:8000</code>.
        </p>
        <button onClick={load} className="btn-ghost px-4 h-10 inline-flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="label-mono mb-2">Pipeline</div>
        <h1 className="font-serif text-4xl tracking-tight">Applications</h1>
        <p className="text-white/55 mt-1 text-[15px]">
          Every job you've applied to via the agent. Click a row to see the cover letter.
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 flex-wrap">
        {Object.entries(counts).map(([id, count]) => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            className={cn(
              "px-3 h-10 rounded-xl text-sm border inline-flex items-center gap-1.5 transition capitalize",
              filter === id
                ? "bg-white/10 border-white/20"
                : "bg-white/[0.02] border-white/5 text-white/55 hover:border-white/10"
            )}
          >
            {id}
            <span className="font-mono text-xs text-white/40">{count}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-white/40 py-12">Loading applications...</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl glass p-10 text-center">
          <Send className="w-10 h-10 mx-auto text-white/30 mb-3" />
          <h3 className="font-serif text-xl mb-2">
            {apps.length === 0 ? "No applications yet" : "No applications match this filter"}
          </h3>
          <p className="text-white/50 text-sm max-w-md mx-auto">
            {apps.length === 0 ? (
              <>
                Go to <Link href="/jobs" className="text-accent hover:underline">Job Search</Link>,
                run a search, then apply to a job to see it here.
              </>
            ) : "Try switching tabs."}
          </p>
        </div>
      ) : (
        <div className="rounded-2xl glass overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                <Th>Role</Th>
                <Th>Company</Th>
                <Th>Mode</Th>
                <Th>Status</Th>
                <Th>Applied</Th>
                <Th>Artifacts</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <ApplicationRow key={a.id} app={a} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ApplicationRow({ app }: { app: Application }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        onClick={() => setExpanded(!expanded)}
        className="border-b border-white/[0.04] hover:bg-white/[0.02] cursor-pointer transition"
      >
        <Td className="font-medium">{app.role}</Td>
        <Td className="text-white/70">{app.company}</Td>
        <Td><ModeBadge mode={app.mode} /></Td>
        <Td><StatusBadge status={app.status} /></Td>
        <Td className="text-white/55 font-mono text-xs">
          {new Date(app.appliedAt).toLocaleDateString()}
        </Td>
        <Td>
          <div className="flex gap-2">
            {app.coverLetter && (
              <span title="Has cover letter" className="text-accent">
                <FileText className="w-3.5 h-3.5" />
              </span>
            )}
            {app.atsPdfUrl && (
              <a
                href={`${API}${app.atsPdfUrl}`}
                target="_blank"
                rel="noopener"
                title="ATS-optimized PDF"
                onClick={(e) => e.stopPropagation()}
                className="text-electric hover:opacity-80"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
            {app.screenshotUrl && (
              <a
                href={`${API}${app.screenshotUrl}`}
                target="_blank"
                rel="noopener"
                title="Screenshot"
                onClick={(e) => e.stopPropagation()}
                className="text-purple hover:opacity-80"
              >
                <ImageIcon className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        </Td>
      </tr>
      {expanded && app.coverLetter && (
        <tr className="bg-white/[0.02]">
          <td colSpan={6} className="p-5">
            <div className="label-mono text-[10px] text-white/40 mb-2">Cover letter</div>
            <pre className="text-sm text-white/80 whitespace-pre-wrap leading-relaxed font-sans max-h-96 overflow-auto">
              {app.coverLetter}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left px-4 py-3 label-mono text-[10px] text-white/40">{children}</th>;
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("px-4 py-3", className)}>{children}</td>;
}
