"use client";

import { useEffect, useState } from "react";
import { Save, X, Plus, AlertCircle, CheckCircle2, RefreshCw, User } from "lucide-react";
import { defaultPrefs } from "@/lib/mockData";
import { cn } from "@/lib/utils";
import type { UserPrefs } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPrefs>(defaultPrefs);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [backendOk, setBackendOk] = useState(true);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [aiInfo, setAiInfo] = useState<any>(null);

  // Tag input state
  const [newRole, setNewRole] = useState("");
  const [newTech, setNewTech] = useState("");
  const [newLocation, setNewLocation] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [pR, hR] = await Promise.all([
        fetch(`${API}/settings/prefs`),
        fetch(`${API}/health`),
      ]);
      if (!pR.ok) throw new Error();
      const data = await pR.json();
      setPrefs({ ...defaultPrefs, ...data });
      if (hR.ok) {
        const h = await hR.json();
        setAiInfo(h.ai);
      }
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    setSaving(true);
    try {
      const r = await fetch(`${API}/settings/prefs`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prefs),
      });
      if (!r.ok) throw new Error();
      setSavedAt(new Date().toLocaleTimeString());
      setTimeout(() => setSavedAt(null), 3000);
    } catch {
      alert("Save failed — backend unreachable");
    } finally {
      setSaving(false);
    }
  }

  function update<K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) {
    setPrefs((p) => ({ ...p, [key]: value }));
  }

  function addToList(key: "targetRoles" | "preferredTech" | "locations", value: string) {
    if (!value.trim()) return;
    const list = prefs[key] || [];
    if (list.includes(value)) return;
    update(key, [...list, value.trim()] as any);
  }

  function removeFromList(key: "targetRoles" | "preferredTech" | "locations", value: string) {
    update(key, (prefs[key] || []).filter((v) => v !== value) as any);
  }

  useEffect(() => { load(); }, []);

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

  if (loading) {
    return <div className="text-center text-white/40 py-12">Loading settings...</div>;
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="label-mono mb-2">Account</div>
          <h1 className="font-serif text-4xl tracking-tight">Settings</h1>
          <p className="text-white/55 mt-1 text-[15px]">
            Personal info and search preferences. Used by the AI to score and apply.
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="btn-primary px-5 h-11 inline-flex items-center gap-2"
        >
          {saving
            ? <><RefreshCw className="w-4 h-4 animate-spin" /> Saving…</>
            : <><Save className="w-4 h-4" /> Save</>}
        </button>
      </div>

      {savedAt && (
        <div className="rounded-xl bg-accent/10 border border-accent/20 text-accent p-3 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Saved at {savedAt}
        </div>
      )}

      {/* Personal */}
      <Section title="Personal info">
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Full name">
            <input value={prefs.fullName || ""} onChange={(e) => update("fullName", e.target.value)} className={inputCls} />
          </Field>
          <Field label="Email">
            <input value={prefs.email || ""} onChange={(e) => update("email", e.target.value)} className={inputCls} />
          </Field>
          <Field label="Phone">
            <input value={prefs.phone || ""} onChange={(e) => update("phone", e.target.value)} className={inputCls} />
          </Field>
          <Field label="Location">
            <input value={prefs.location || ""} onChange={(e) => update("location", e.target.value)} className={inputCls} />
          </Field>
        </div>
      </Section>

      {/* Target roles */}
      <Section title="Target roles" subtitle="Job titles the AI looks for">
        <TagList
          values={prefs.targetRoles || []}
          onAdd={(v) => addToList("targetRoles", v)}
          onRemove={(v) => removeFromList("targetRoles", v)}
          newValue={newRole}
          setNewValue={setNewRole}
          placeholder="e.g. Senior Full Stack Engineer"
        />
      </Section>

      {/* Preferred tech */}
      <Section title="Preferred tech stack" subtitle="Boosts match score when overlapping with job listings">
        <TagList
          values={prefs.preferredTech || []}
          onAdd={(v) => addToList("preferredTech", v)}
          onRemove={(v) => removeFromList("preferredTech", v)}
          newValue={newTech}
          setNewValue={setNewTech}
          placeholder="e.g. Next.js"
        />
      </Section>

      {/* Work mode */}
      <Section title="Work mode">
        <div className="grid grid-cols-3 gap-3">
          <ModeToggle label="Remote" value={prefs.remote} onChange={(v) => update("remote", v)} />
          <ModeToggle label="Hybrid" value={prefs.hybrid} onChange={(v) => update("hybrid", v)} />
          <ModeToggle label="Onsite" value={prefs.onsite} onChange={(v) => update("onsite", v)} />
        </div>
      </Section>

      {/* Salary */}
      <Section title="Minimum salary">
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Permanent (per year, £)">
            <input
              type="number"
              value={prefs.minSalaryPermanent || 0}
              onChange={(e) => update("minSalaryPermanent", Number(e.target.value))}
              className={inputCls}
            />
          </Field>
          <Field label="Contract (per day, £)">
            <input
              type="number"
              value={prefs.minSalaryContract || 0}
              onChange={(e) => update("minSalaryContract", Number(e.target.value))}
              className={inputCls}
            />
          </Field>
        </div>
      </Section>

      {/* Preferred locations */}
      <Section title="Preferred locations">
        <TagList
          values={prefs.locations || []}
          onAdd={(v) => addToList("locations", v)}
          onRemove={(v) => removeFromList("locations", v)}
          newValue={newLocation}
          setNewValue={setNewLocation}
          placeholder="e.g. UK Remote"
        />
      </Section>

      {/* AI provider info */}
      {aiInfo && (
        <Section title="AI provider" subtitle="Configured via backend/.env — restart backend to change">
          <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-5 space-y-2">
            <Row label="Provider" value={aiInfo.provider} mono />
            <Row label="Model" value={aiInfo.model || "—"} mono />
            <Row label="Base URL" value={aiInfo.baseUrl || "—"} mono />
            <Row
              label="Status"
              value={aiInfo.configured ? "configured ✓" : "no API key — fallback heuristics"}
              accent={aiInfo.configured ? "text-accent" : "text-warn"}
            />
          </div>
        </Section>
      )}
    </div>
  );
}

const inputCls = "w-full bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-lg h-10 px-3 text-sm";

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-serif text-2xl mb-1">{title}</h2>
      {subtitle && <p className="text-sm text-white/55 mb-4">{subtitle}</p>}
      {!subtitle && <div className="mb-4" />}
      <div>{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="label-mono text-[10px] text-white/50 mb-1.5 block">{label}</span>
      {children}
    </label>
  );
}

function TagList({
  values, onAdd, onRemove, newValue, setNewValue, placeholder,
}: {
  values: string[];
  onAdd: (v: string) => void;
  onRemove: (v: string) => void;
  newValue: string;
  setNewValue: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {values.map((v) => (
          <span
            key={v}
            className="px-3 py-1.5 rounded-md bg-white/[0.04] border border-white/[0.06] text-sm inline-flex items-center gap-2"
          >
            {v}
            <button
              onClick={() => onRemove(v)}
              className="text-white/40 hover:text-danger transition"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd(newValue);
              setNewValue("");
            }
          }}
          placeholder={placeholder}
          className={inputCls + " flex-1"}
        />
        <button
          onClick={() => { onAdd(newValue); setNewValue(""); }}
          className="btn-ghost px-3 h-10 inline-flex items-center gap-1.5 shrink-0"
        >
          <Plus className="w-4 h-4" /> Add
        </button>
      </div>
    </div>
  );
}

function ModeToggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={cn(
        "px-4 h-12 rounded-xl border text-sm transition",
        value
          ? "bg-accent/10 border-accent/30 text-accent"
          : "bg-white/[0.02] border-white/[0.06] text-white/60 hover:border-white/15"
      )}
    >
      {label}
    </button>
  );
}

function Row({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: string }) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-white/50">{label}</span>
      <span className={cn(mono && "font-mono text-xs", accent ? accent : "text-white/85")}>
        {value}
      </span>
    </div>
  );
}
