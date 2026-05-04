"use client";

import { useEffect, useRef, useState } from "react";
import { Building2, Star, Ban, Plus, X, Radar, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const initialFavs = ["Vercel", "Anthropic", "Supabase", "Stripe", "Linear"];
const initialBlocked = ["Spam Recruiter Co", "MLM Software Ltd"];

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type DiscoveryState = {
  status: "idle" | "running" | "done" | "error";
  tested: number;
  total: number;
  found: Record<string, number>;
  startedAt: string | null;
  finishedAt: string | null;
  error: string | null;
};

type StoreData = {
  updatedAt: string | null;
  stats: Record<string, number>;
  candidatesTested: number;
};

export default function CompaniesPage() {
  const [favs, setFavs] = useState(initialFavs);
  const [blocked, setBlocked] = useState(initialBlocked);
  const [newFav, setNewFav] = useState("");
  const [newBlock, setNewBlock] = useState("");

  const [discovery, setDiscovery] = useState<DiscoveryState | null>(null);
  const [store, setStore] = useState<StoreData | null>(null);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Initial fetch
  useEffect(() => {
    fetchStatus();
    fetchStore();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchStatus() {
    try {
      const r = await fetch(`${API}/companies/discovery-status`);
      if (!r.ok) return;
      const data: DiscoveryState = await r.json();
      setDiscovery(data);
      if (data.status === "running" && !pollRef.current) startPolling();
      if (data.status !== "running" && pollRef.current) stopPolling();
    } catch { /* backend offline — ignore */ }
  }

  async function fetchStore() {
    try {
      const r = await fetch(`${API}/companies/lists`);
      if (!r.ok) return;
      const data = await r.json();
      setStore(data.store);
    } catch { /* ignore */ }
  }

  function startPolling() {
    if (pollRef.current) return;
    pollRef.current = setInterval(fetchStatus, 1500);
  }
  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    fetchStore();
  }

  async function startDiscovery() {
    setBusy(true);
    try {
      const r = await fetch(`${API}/companies/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mergeWithExisting: true }),
      });
      const data = await r.json();
      if (data.state) setDiscovery(data.state);
      startPolling();
    } catch {
      alert("Backend not reachable. Make sure FastAPI is running on port 8000.");
    } finally {
      setBusy(false);
    }
  }

  const isRunning = discovery?.status === "running";
  const totalFound = discovery
    ? Object.values(discovery.found).reduce((a, b) => a + b, 0)
    : 0;
  const totalStored = store
    ? Object.values(store.stats || {}).reduce((a, b) => a + b, 0)
    : 0;
  const progressPct = discovery && discovery.total > 0
    ? Math.round((discovery.tested / discovery.total) * 100)
    : 0;

  return (
    <div className="space-y-8">
      <div>
        <div className="label-mono mb-2">Companies</div>
        <h1 className="font-serif text-4xl tracking-tight">Watchlist & blocklist</h1>
        <p className="text-white/55 mt-1 text-[15px]">
          Boost matches for companies you love. Skip ones you never want to hear from.
        </p>
      </div>

      {/* Discovery panel */}
      <div className="rounded-2xl glass p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-electric/10 border border-electric/30 flex items-center justify-center">
            <Radar className="w-5 h-5 text-electric" />
          </div>
          <div className="flex-1">
            <h2 className="font-serif text-2xl">Auto-discover ATS-hosted companies</h2>
            <div className="text-sm text-white/55 mt-1">
              Scans 690+ candidate slugs against Greenhouse, Lever, Ashby, Workable and SmartRecruiters
              APIs in parallel. Takes ~2-5 minutes. Results saved to <span className="font-mono text-xs">companies.json</span>.
            </div>
          </div>
          <button
            onClick={startDiscovery}
            disabled={isRunning || busy}
            className={cn(
              "btn-primary px-5 h-11 inline-flex items-center gap-2 whitespace-nowrap",
              (isRunning || busy) && "opacity-60 cursor-not-allowed"
            )}
          >
            {isRunning ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Running…</>
            ) : (
              <><Radar className="w-4 h-4" /> Run discovery</>
            )}
          </button>
        </div>

        {/* Progress bar */}
        {discovery && discovery.status !== "idle" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-mono text-white/60">
              <span>
                {discovery.status === "running" && (
                  <>Tested {discovery.tested} / {discovery.total}</>
                )}
                {discovery.status === "done" && (
                  <span className="text-accent inline-flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Done — {totalFound} companies discovered
                  </span>
                )}
                {discovery.status === "error" && (
                  <span className="text-danger inline-flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" /> {discovery.error}
                  </span>
                )}
              </span>
              <span>{progressPct}%</span>
            </div>
            <div className="h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-electric to-accent transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2">
              {(["greenhouse", "lever", "ashby", "workable", "smartrecruiters"] as const).map((k) => (
                <div key={k} className="rounded-lg bg-white/[0.03] border border-white/[0.05] p-3">
                  <div className="label-mono text-[10px] text-white/50">{k}</div>
                  <div className="font-mono text-xl mt-0.5">{discovery.found[k] ?? 0}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stored stats */}
        {store && totalStored > 0 && discovery?.status !== "running" && (
          <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between text-xs">
            <span className="text-white/50">
              <span className="font-mono text-accent">{totalStored}</span> companies currently in <span className="font-mono">companies.json</span>
            </span>
            {store.updatedAt && (
              <span className="text-white/40 font-mono">
                Updated {new Date(store.updatedAt).toLocaleString()}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <CompanyList
          title="Favourite companies"
          icon={<Star className="w-4 h-4 text-accent" />}
          tone="accent"
          items={favs}
          input={newFav}
          setInput={setNewFav}
          onAdd={() => {
            if (newFav.trim()) {
              setFavs([...favs, newFav.trim()]);
              setNewFav("");
            }
          }}
          onRemove={(v) => setFavs(favs.filter((f) => f !== v))}
          placeholder="Add a company you'd love to work for…"
          subtitle="Match score gets a +5 boost"
        />

        <CompanyList
          title="Blocked companies"
          icon={<Ban className="w-4 h-4 text-danger" />}
          tone="danger"
          items={blocked}
          input={newBlock}
          setInput={setNewBlock}
          onAdd={() => {
            if (newBlock.trim()) {
              setBlocked([...blocked, newBlock.trim()]);
              setNewBlock("");
            }
          }}
          onRemove={(v) => setBlocked(blocked.filter((b) => b !== v))}
          placeholder="Add a company to skip entirely…"
          subtitle="Jobs from these companies are never shown"
        />
      </div>
    </div>
  );
}

function CompanyList({
  title,
  icon,
  tone,
  items,
  input,
  setInput,
  onAdd,
  onRemove,
  placeholder,
  subtitle
}: {
  title: string;
  icon: React.ReactNode;
  tone: "accent" | "danger";
  items: string[];
  input: string;
  setInput: (v: string) => void;
  onAdd: () => void;
  onRemove: (v: string) => void;
  placeholder: string;
  subtitle: string;
}) {
  return (
    <div className="rounded-2xl glass p-6">
      <div className="flex items-start gap-3 mb-1">
        {icon}
        <div className="flex-1">
          <h2 className="font-serif text-2xl">{title}</h2>
          <div className="text-xs text-white/50 mt-0.5">{subtitle}</div>
        </div>
        <span className="font-mono text-xs text-white/40">{items.length}</span>
      </div>

      <div className="flex gap-2 mt-4 mb-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), onAdd())}
          placeholder={placeholder}
          className="flex-1 bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-lg h-10 px-3 text-sm"
        />
        <button onClick={onAdd} className="btn-ghost px-3">
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
        {items.length === 0 ? (
          <div className="text-sm text-white/40 py-3">No entries yet.</div>
        ) : (
          items.map((c) => (
            <div
              key={c}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg border",
                tone === "accent"
                  ? "bg-accent/[0.04] border-accent/15"
                  : "bg-danger/[0.04] border-danger/15"
              )}
            >
              <Building2 className={cn("w-4 h-4", tone === "accent" ? "text-accent" : "text-danger")} />
              <span className="flex-1 text-sm">{c}</span>
              <button
                onClick={() => onRemove(c)}
                className="text-white/40 hover:text-danger transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
