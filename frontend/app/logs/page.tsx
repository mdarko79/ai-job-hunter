"use client";

import { useEffect, useState } from "react";
import { Activity, Filter, RefreshCw, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "success" | "warn" | "error" | string;
  source: string;
  message: string;
}

const LEVELS = ["all", "success", "info", "warn", "error"];

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState("all");
  const [source, setSource] = useState("all");
  const [loading, setLoading] = useState(true);
  const [backendOk, setBackendOk] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/logs?limit=500`);
      if (!r.ok) throw new Error();
      setLogs(await r.json());
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const sources = ["all", ...Array.from(new Set(logs.map((l) => l.source)))];
  const filtered = logs.filter((l) => {
    if (level !== "all" && l.level !== level) return false;
    if (source !== "all" && l.source !== source) return false;
    return true;
  });

  if (!backendOk) {
    return (
      <div className="rounded-2xl glass p-8 text-center">
        <AlertCircle className="w-10 h-10 text-warn mx-auto mb-3" />
        <h2 className="font-serif text-2xl mb-2">Backend not reachable</h2>
        <p className="text-white/55 text-sm">FastAPI must be running on port 8000.</p>
        <button onClick={load} className="btn-ghost px-4 h-10 mt-4 inline-flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="label-mono mb-2">Activity</div>
          <h1 className="font-serif text-4xl tracking-tight">Logs</h1>
          <p className="text-white/55 mt-1 text-[15px]">
            Everything the agent has done. Auto-refreshes every 10 seconds.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="btn-ghost px-4 h-10 inline-flex items-center gap-2"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="flex gap-1.5">
          {LEVELS.map((l) => (
            <button
              key={l}
              onClick={() => setLevel(l)}
              className={cn(
                "px-3 h-9 rounded-lg text-xs border inline-flex items-center gap-1.5 transition capitalize",
                level === l
                  ? "bg-white/10 border-white/20"
                  : "bg-white/[0.02] border-white/5 text-white/55 hover:border-white/10"
              )}
            >
              <span className={cn(
                "w-1.5 h-1.5 rounded-full",
                l === "success" && "bg-accent",
                l === "info" && "bg-electric",
                l === "warn" && "bg-warn",
                l === "error" && "bg-danger",
                l === "all" && "bg-white/40",
              )} />
              {l}
            </button>
          ))}
        </div>

        {sources.length > 1 && (
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-lg h-9 px-3 text-xs"
          >
            {sources.map((s, i) => (
              <option key={`${s}-${i}`} value={s} className="bg-ink-950">
                {s === "all" ? "All sources" : s}
              </option>
            ))}
          </select>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl glass p-10 text-center">
          <Activity className="w-10 h-10 mx-auto text-white/30 mb-3" />
          <h3 className="font-serif text-xl mb-2">
            {logs.length === 0 ? "No logs yet" : "No logs match filters"}
          </h3>
          <p className="text-white/50 text-sm">
            {logs.length === 0 && "Logs appear when the agent does anything — searches, scoring, applies."}
          </p>
        </div>
      ) : (
        <div className="rounded-2xl glass divide-y divide-white/[0.04]">
          {filtered.map((log) => (
            <div key={log.id} className="flex items-start gap-3 p-3 hover:bg-white/[0.02] transition">
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
              <span className={cn(
                "text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded shrink-0",
                log.level === "success" && "bg-accent/10 text-accent",
                log.level === "error" && "bg-danger/10 text-danger",
                log.level === "warn" && "bg-warn/10 text-warn",
                log.level === "info" && "bg-electric/10 text-electric",
              )}>
                {log.level}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
