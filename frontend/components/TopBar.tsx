"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Bell, Search, Command, X, AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Job {
  id: string;
  role: string;
  company: string;
  matchScore: number;
}

interface LogEntry {
  id: string;
  timestamp: string;
  level: string;
  source: string;
  message: string;
}

export function TopBar() {
  const router = useRouter();

  // Search state
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Job[]>([]);
  const [allJobs, setAllJobs] = useState<Job[]>([]);
  const searchRef = useRef<HTMLDivElement>(null);

  // Notifications state
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifs, setNotifs] = useState<LogEntry[]>([]);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const notifRef = useRef<HTMLDivElement>(null);

  // Fetch jobs once for search
  useEffect(() => {
    fetch(`${API}/jobs`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setAllJobs(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, []);

  // Poll logs for notifications
  useEffect(() => {
    let stopped = false;
    async function poll() {
      try {
        const r = await fetch(`${API}/logs?limit=20`);
        if (!r.ok) return;
        const data: LogEntry[] = await r.json();
        if (!stopped) setNotifs(data);
      } catch {}
    }
    poll();
    const t = setInterval(poll, 30000);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, []);

  // Filter jobs by query (client-side, fast)
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const q = query.toLowerCase();
    const filtered = allJobs
      .filter((j) =>
        `${j.role} ${j.company}`.toLowerCase().includes(q)
      )
      .slice(0, 8);
    setResults(filtered);
  }, [query, allJobs]);

  // Close popovers on outside click + cmd-K
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const unreadCount = notifs.filter(
    (n) => !seenIds.has(n.id) && (n.level === "error" || n.level === "warn" || n.level === "success")
  ).length;

  function markAllRead() {
    setSeenIds(new Set(notifs.map((n) => n.id)));
  }

  function pickJob(j: Job) {
    setSearchOpen(false);
    setQuery("");
    router.push(`/jobs`);
  }

  return (
    <header className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/50 border-b border-white/[0.05]">
      <div className="flex items-center gap-4 px-6 lg:px-10 h-14 max-w-[1600px] mx-auto w-full">
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-white/40">
          <span>Operations</span>
          <span className="text-white/20">/</span>
          <span className="text-white/70">Console</span>
        </div>

        <div className="flex-1" />

        {/* Search */}
        <div className="relative" ref={searchRef}>
          <button
            onClick={() => setSearchOpen(true)}
            className="hidden lg:flex items-center gap-2 h-9 px-3 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition text-sm text-white/50"
          >
            <Search className="w-4 h-4" />
            <span>Search jobs, companies…</span>
            <span className="ml-6 flex items-center gap-1 text-[10px] font-mono text-white/30">
              <Command className="w-3 h-3" /> K
            </span>
          </button>

          {searchOpen && (
            <div className="absolute right-0 top-12 w-[480px] rounded-xl bg-ink-950/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 h-12 border-b border-white/[0.06]">
                <Search className="w-4 h-4 text-white/40" />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={`Search ${allJobs.length} jobs by role or company…`}
                  className="flex-1 bg-transparent outline-none text-sm placeholder:text-white/30"
                />
                {query && (
                  <button onClick={() => setQuery("")} className="text-white/40 hover:text-white">
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <div className="max-h-96 overflow-auto">
                {!query.trim() ? (
                  <div className="p-6 text-center text-xs text-white/40">
                    Type to search across all loaded jobs.
                  </div>
                ) : results.length === 0 ? (
                  <div className="p-6 text-center text-xs text-white/40">
                    No matches in the current pipeline.
                  </div>
                ) : (
                  results.map((j) => (
                    <button
                      key={`${j.id}-${i}`}
                      onClick={() => pickJob(j)}
                      className="w-full flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-white/[0.04] transition text-left"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{j.role}</div>
                        <div className="text-[11px] text-white/45 font-mono truncate">
                          {j.company}
                        </div>
                      </div>
                      <span
                        className={cn(
                          "text-[11px] font-mono px-2 py-0.5 rounded shrink-0",
                          j.matchScore >= 80
                            ? "bg-accent/15 text-accent"
                            : j.matchScore >= 60
                              ? "bg-warn/15 text-warn"
                              : "bg-white/5 text-white/50"
                        )}
                      >
                        {j.matchScore}%
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => {
              setNotifOpen(!notifOpen);
              if (!notifOpen) markAllRead();
            }}
            className="relative w-9 h-9 grid place-items-center rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition"
          >
            <Bell className="w-4 h-4 text-white/70" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent grid place-items-center text-[9px] font-mono text-ink-950 font-bold">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 top-12 w-[400px] rounded-xl bg-ink-950/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between px-4 h-11 border-b border-white/[0.06]">
                <div className="text-sm font-medium">Activity</div>
                <Link
                  href="/logs"
                  onClick={() => setNotifOpen(false)}
                  className="text-[11px] text-white/50 hover:text-white"
                >
                  View all logs →
                </Link>
              </div>
              <div className="max-h-96 overflow-auto">
                {notifs.length === 0 ? (
                  <div className="p-6 text-center text-xs text-white/40">
                    No activity yet. Run a job search.
                  </div>
                ) : (
                  notifs.slice(0, 10).map((n, i) => <NotifRow key={`${n.id}-${i}`} log={n} />)
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 pl-3 ml-1 border-l border-white/[0.06]">
          <div className="text-right leading-tight hidden sm:block">
            <div className="text-sm font-medium">You</div>
            <div className="text-[11px] text-white/40 font-mono">Manchester, UK</div>
          </div>
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-electric via-accent to-purple grid place-items-center text-ink-950 font-semibold text-sm">
            J
          </div>
        </div>
      </div>
    </header>
  );
}

function NotifRow({ log }: { log: LogEntry }) {
  const Icon =
    log.level === "error" ? AlertCircle :
    log.level === "warn" ? AlertTriangle :
    log.level === "success" ? CheckCircle2 :
    Info;
  const color =
    log.level === "error" ? "text-danger" :
    log.level === "warn" ? "text-warn" :
    log.level === "success" ? "text-accent" :
    "text-electric";

  return (
    <div className="flex items-start gap-3 px-4 py-2.5 hover:bg-white/[0.03] transition border-b border-white/[0.04] last:border-0">
      <Icon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", color)} />
      <div className="flex-1 min-w-0">
        <div className="text-[13px] text-white/85 leading-snug">{log.message}</div>
        <div className="text-[10px] font-mono text-white/40 mt-0.5">
          {new Date(log.timestamp).toLocaleTimeString()} · {log.source}
        </div>
      </div>
    </div>
  );
}
