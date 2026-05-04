"use client";

import { useEffect, useState } from "react";
import {
  Shield,
  Sparkles,
  AlertTriangle,
  Lock,
  Save,
  Camera,
  Building2,
  Ban,
  Plus,
  X,
  RefreshCw,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { defaultRules } from "@/lib/mockData";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RulesPage() {
  const [rules, setRules] = useState(defaultRules);
  const [newCompany, setNewCompany] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/settings/rules`);
      if (!r.ok) throw new Error();
      const data = await r.json();
      setRules({ ...defaultRules, ...data });
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
      const { hardLimitMaxPerDay, ...payload } = rules as any;
      const r = await fetch(`${API}/settings/rules`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Save failed");
      }
      setSavedAt(new Date().toLocaleTimeString());
      setTimeout(() => setSavedAt(null), 3000);
    } catch (e: any) {
      alert(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => { load(); }, []);

  const update = <K extends keyof typeof rules>(key: K, value: (typeof rules)[K]) =>
    setRules((r) => ({ ...r, [key]: value }));

  const addToList = (key: "blacklistCompanies" | "blacklistKeywords", val: string) => {
    if (!val.trim()) return;
    setRules((r) => ({ ...r, [key]: [...r[key], val.trim()] }));
  };
  const removeFromList = (key: "blacklistCompanies" | "blacklistKeywords", val: string) => {
    setRules((r) => ({ ...r, [key]: r[key].filter((v) => v !== val) }));
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="label-mono mb-2">Auto Apply Rules</div>
          <h1 className="font-serif text-4xl tracking-tight">
            Guardrails for your <span className="italic text-gradient-accent">autonomous</span> agent
          </h1>
          <p className="text-white/55 mt-1 text-[15px] max-w-2xl">
            The agent will only auto-apply when every rule is satisfied. Anything else falls back
            to draft-ready or review.
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving || loading}
          className="btn-primary inline-flex items-center gap-2"
        >
          {saving
            ? <><RefreshCw className="w-4 h-4 animate-spin" /> Saving…</>
            : <><Save className="w-4 h-4" /> Save rules</>}
        </button>
      </div>

      {!backendOk && (
        <div className="rounded-xl bg-warn/10 border border-warn/20 text-warn p-3 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Backend not reachable — changes won't be saved. Start FastAPI on port 8000 then refresh.
        </div>
      )}
      {savedAt && (
        <div className="rounded-xl bg-accent/10 border border-accent/20 text-accent p-3 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Saved at {savedAt}
        </div>
      )}

      {/* Master switch */}
      <div className="relative overflow-hidden rounded-2xl glass-strong p-6 noise">
        <div className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-accent/10 blur-3xl pointer-events-none" />
        <div className="flex items-center gap-5 relative">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent/30 to-electric/30 grid place-items-center">
            <Shield className="w-5 h-5 text-accent" />
          </div>
          <div className="flex-1">
            <div className="font-serif text-2xl">Auto Apply Mode</div>
            <p className="text-white/55 text-sm mt-0.5">
              Allow the agent to submit applications without your approval (within rules).
            </p>
          </div>
          <Toggle value={rules.enabled} onChange={(v) => update("enabled", v)} />
        </div>
      </div>

      {/* Daily limit — STAR FEATURE */}
      <Section title="Daily volume" icon={Sparkles} accent="accent">
        <div className="rounded-xl bg-gradient-to-br from-accent/5 to-electric/5 border border-white/[0.06] p-6">
          <div className="flex items-baseline justify-between gap-4 mb-4 flex-wrap">
            <div>
              <div className="label-mono mb-1">Max applications per day</div>
              <div className="text-sm text-white/55">
                Hard cap. Once reached, the agent stops until tomorrow.
              </div>
            </div>
            <div className="font-serif text-5xl text-gradient-accent leading-none">
              {rules.maxPerDay}
            </div>
          </div>

          <input
            type="range"
            min={1}
            max={100}
            value={rules.maxPerDay}
            onChange={(e) => update("maxPerDay", Number(e.target.value))}
            className="w-full"
            aria-label="Max applications per day"
          />

          <div className="mt-2 flex justify-between text-[10px] font-mono text-white/30 uppercase tracking-[0.18em]">
            <span>1</span>
            <span>25</span>
            <span>50</span>
            <span>75</span>
            <span>100</span>
          </div>

          <div className="mt-5 grid grid-cols-4 gap-2">
            {[5, 10, 25, 100].map((preset) => (
              <button
                key={preset}
                onClick={() => update("maxPerDay", preset)}
                className={cn(
                  "h-9 rounded-lg text-xs font-medium border transition",
                  rules.maxPerDay === preset
                    ? "bg-accent/15 border-accent/30 text-accent"
                    : "bg-white/[0.03] border-white/[0.06] text-white/60 hover:text-white"
                )}
              >
                {preset === 5
                  ? "Cautious"
                  : preset === 10
                    ? "Default"
                    : preset === 25
                      ? "Aggressive"
                      : "Max"}
                <span className="ml-1.5 font-mono text-white/40">{preset}</span>
              </button>
            ))}
          </div>

          {rules.maxPerDay >= 50 && (
            <div className="mt-4 rounded-lg border border-warn/20 bg-warn/[0.05] px-3 py-2.5 flex gap-2 items-start text-[13px]">
              <AlertTriangle className="w-4 h-4 text-warn shrink-0 mt-0.5" />
              <div className="text-white/75">
                <span className="text-warn font-medium">High volume.</span> {rules.maxPerDay}+ daily
                applies may trigger anti-spam systems on LinkedIn and other platforms. Consider
                spreading across sources.
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* Match score */}
      <Section title="Match quality" icon={Sparkles} accent="electric">
        <SliderCard
          label="Minimum match score"
          description="Reject anything scored below this threshold."
          value={rules.minMatchScore}
          min={50}
          max={100}
          suffix="%"
          onChange={(v) => update("minMatchScore", v)}
        />
      </Section>

      {/* Salary */}
      <Section title="Compensation floor" icon={Lock} accent="electric">
        <div className="grid sm:grid-cols-2 gap-3">
          <NumberCard
            label="Min permanent salary"
            description="Annual, GBP"
            value={rules.minSalaryPermanent}
            prefix="£"
            step={1000}
            onChange={(v) => update("minSalaryPermanent", v)}
          />
          <NumberCard
            label="Min contract day rate"
            description="GBP per day"
            value={rules.minSalaryContract}
            prefix="£"
            suffix="/day"
            step={25}
            onChange={(v) => update("minSalaryContract", v)}
          />
        </div>
      </Section>

      {/* Work mode */}
      <Section title="Work mode" icon={Building2} accent="purple">
        <div className="grid sm:grid-cols-3 gap-3">
          {(["remote", "hybrid", "onsite"] as const).map((mode) => (
            <ToggleCard
              key={mode}
              label={mode.charAt(0).toUpperCase() + mode.slice(1)}
              description={
                mode === "remote"
                  ? "Fully remote"
                  : mode === "hybrid"
                    ? "Some days in office"
                    : "Office every day"
              }
              checked={rules.workModes.includes(mode)}
              onChange={(checked) =>
                update(
                  "workModes",
                  checked
                    ? [...rules.workModes, mode]
                    : rules.workModes.filter((m) => m !== mode)
                )
              }
            />
          ))}
        </div>
        <SliderCard
          label="Max days in office (for hybrid)"
          description="Reject hybrid roles that require more than this many days on-site."
          value={rules.maxDaysInOffice}
          min={0}
          max={5}
          suffix="d"
          onChange={(v) => update("maxDaysInOffice", v)}
        />
      </Section>

      {/* Safety */}
      <Section title="Safety & approval" icon={Shield} accent="accent">
        <div className="space-y-2.5">
          <SwitchRow
            label="Require approval for LinkedIn"
            description="LinkedIn applies are flagged for manual review even if all rules pass."
            value={rules.requireApprovalLinkedIn}
            onChange={(v) => update("requireApprovalLinkedIn", v)}
          />
          <SwitchRow
            label="Require salary disclosed"
            description="Skip jobs with no published salary range."
            value={rules.requireSalary}
            onChange={(v) => update("requireSalary", v)}
          />
          <SwitchRow
            label={
              <>
                Save screenshot before submit <Camera className="w-3.5 h-3.5 inline ml-1" />
              </>
            }
            description="Capture the filled form before pressing Submit (highly recommended)."
            value={rules.saveScreenshots}
            onChange={(v) => update("saveScreenshots", v)}
          />
        </div>
      </Section>

      {/* Blacklists */}
      <Section title="Blacklists" icon={Ban} accent="warn">
        <div className="grid lg:grid-cols-2 gap-4">
          <BlacklistCard
            title="Companies"
            placeholder="e.g. Acme Corp"
            items={rules.blacklistCompanies}
            input={newCompany}
            setInput={setNewCompany}
            onAdd={() => {
              addToList("blacklistCompanies", newCompany);
              setNewCompany("");
            }}
            onRemove={(v) => removeFromList("blacklistCompanies", v)}
          />
          <BlacklistCard
            title="Keywords"
            placeholder="e.g. unpaid, internship"
            items={rules.blacklistKeywords}
            input={newKeyword}
            setInput={setNewKeyword}
            onAdd={() => {
              addToList("blacklistKeywords", newKeyword);
              setNewKeyword("");
            }}
            onRemove={(v) => removeFromList("blacklistKeywords", v)}
          />
        </div>
      </Section>

      {/* ===== Quality Features (career-ops style) ===== */}
      <Section
        title="Quality features"
        subtitle="Optional features inspired by career-ops. Off by default — flip the master switch to opt in."
        icon={Sparkles}
      >
        <div className="space-y-4">
          <div className={cn(
            "rounded-xl border p-5 transition",
            rules.qualityMode
              ? "bg-purple/[0.04] border-purple/30"
              : "bg-white/[0.02] border-white/[0.06]"
          )}>
            <div className="flex items-start gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium">Quality mode</h3>
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-purple/10 text-purple font-mono uppercase tracking-wider">Master toggle</span>
                </div>
                <p className="text-sm text-white/55">
                  When on, the agent prioritises <strong className="text-white/75">quality over volume</strong>:
                  ranks by overall grade, hides anything below your threshold, and disables Auto-Apply mode
                  unless explicitly re-enabled. Recommended if you're applying to senior/staff roles.
                </p>
              </div>
              <Toggle value={rules.qualityMode} onChange={(v) => update("qualityMode", v)} />
            </div>
          </div>

          <FeatureRow
            title="10-dimension A-F scoring"
            description="Score each job across role-fit, tech-fit, comp-fit, location-fit, culture, growth, learning, company health and application cost. Slower but far more honest than a single match %."
            value={rules.multiDimScoring}
            onChange={(v) => update("multiDimScoring", v)}
          />

          {rules.multiDimScoring && rules.qualityMode && (
            <div className="ml-8 pl-4 border-l border-purple/30">
              <label className="block">
                <span className="text-sm text-white/70 mb-2 block">
                  Hide jobs below grade <span className="text-purple font-mono ml-1">{rules.minOverallGrade}</span>
                </span>
                <div className="flex gap-1.5">
                  {(["A", "B", "C", "D"] as const).map((g) => (
                    <button
                      key={g}
                      onClick={() => update("minOverallGrade", g)}
                      className={cn(
                        "px-3 py-1.5 rounded-md font-mono text-xs border transition",
                        rules.minOverallGrade === g
                          ? "bg-purple/15 border-purple/40 text-purple"
                          : "bg-white/[0.03] border-white/10 text-white/55 hover:border-white/20"
                      )}
                    >
                      {g}+
                    </button>
                  ))}
                </div>
              </label>
            </div>
          )}

          <FeatureRow
            title="Auto-generate ATS-optimized PDF on every apply"
            description="On each application, AI extracts keywords from the job description and rewrites your CV (without lying) so it passes ATS screening. Output: PDF saved with the application."
            value={rules.autoGenerateATSPDF}
            onChange={(v) => update("autoGenerateATSPDF", v)}
          />

          <FeatureRow
            title="Auto-build Story Bank from applications"
            description="After every apply, AI mines your CV for STAR+R behavioural stories relevant to that role. After ~5 applications you'll have 5-10 master stories ready for interviews. View on the Story Bank page."
            value={rules.autoGenerateStories}
            onChange={(v) => update("autoGenerateStories", v)}
          />

          <FeatureRow
            title="Enable Wellfound (formerly AngelList)"
            description="Wellfound has no public API — this uses Playwright with your session cookie. Works, but their ToS prohibits automation. Use at your own risk."
            value={rules.enableWellfound}
            onChange={(v) => update("enableWellfound", v)}
            warning
          />
          {rules.enableWellfound && (
            <div className="ml-8 pl-4 border-l border-warn/30 space-y-2">
              <label className="block">
                <span className="text-xs text-white/55 mb-1 block">
                  Paste your <code className="text-warn">wellfound_session</code> cookie
                  (DevTools → Application → Cookies → wellfound.com):
                </span>
                <input
                  type="password"
                  value={rules.wellfoundCookie}
                  onChange={(e) => update("wellfoundCookie", e.target.value)}
                  placeholder="Long base64-ish string..."
                  className="w-full bg-white/[0.03] border border-white/[0.06] focus:border-warn/40 outline-none rounded-lg h-10 px-3 text-sm font-mono"
                />
              </label>
              <p className="text-[11px] text-white/40">
                Stored locally in your SQLite. Never sent anywhere except wellfound.com.
              </p>
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}

function FeatureRow({
  title,
  description,
  value,
  onChange,
  warning,
}: {
  title: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
  warning?: boolean;
}) {
  return (
    <div className={cn(
      "flex items-start gap-4 p-4 rounded-xl border",
      value
        ? warning
          ? "bg-warn/[0.04] border-warn/25"
          : "bg-accent/[0.03] border-accent/20"
        : "bg-white/[0.02] border-white/[0.05]"
    )}>
      <div className="flex-1 min-w-0">
        <h4 className="font-medium text-sm mb-1">{title}</h4>
        <p className="text-xs text-white/55 leading-relaxed">{description}</p>
      </div>
      <Toggle value={value} onChange={onChange} />
    </div>
  );
}

/* ------- helpers ------- */

function Section({
  title,
  subtitle,
  icon: Icon,
  accent = "accent",
  children
}: {
  title: string;
  subtitle?: string;
  icon: any;
  accent?: "accent" | "electric" | "warn" | "purple";
  children: React.ReactNode;
}) {
  const tone = {
    accent: "text-accent",
    electric: "text-electric-glow",
    warn: "text-warn",
    purple: "text-purple"
  }[accent];

  return (
    <section>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={cn("w-4 h-4", tone)} />
        <h2 className="font-serif text-2xl">{title}</h2>
      </div>
      {subtitle && (
        <p className="text-sm text-white/55 mb-3 ml-6">{subtitle}</p>
      )}
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={cn(
        "relative w-12 h-7 rounded-full transition-colors duration-200",
        value ? "bg-gradient-to-br from-accent to-accent-dim shadow-glow" : "bg-white/[0.08]"
      )}
    >
      <span
        className={cn(
          "absolute top-1 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-200",
          value ? "translate-x-6" : "translate-x-1"
        )}
      />
    </button>
  );
}

function SwitchRow({
  label,
  description,
  value,
  onChange
}: {
  label: React.ReactNode;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl glass p-4">
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{label}</div>
        <div className="text-xs text-white/50 mt-0.5">{description}</div>
      </div>
      <Toggle value={value} onChange={onChange} />
    </div>
  );
}

function SliderCard({
  label,
  description,
  value,
  min,
  max,
  suffix,
  onChange
}: {
  label: string;
  description: string;
  value: number;
  min: number;
  max: number;
  suffix?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="rounded-xl glass p-5">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <div className="font-medium text-sm">{label}</div>
          <div className="text-xs text-white/50 mt-0.5">{description}</div>
        </div>
        <div className="font-serif text-3xl text-gradient-accent">
          {value}
          {suffix}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
    </div>
  );
}

function NumberCard({
  label,
  description,
  value,
  prefix,
  suffix,
  step,
  onChange
}: {
  label: string;
  description: string;
  value: number;
  prefix?: string;
  suffix?: string;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="rounded-xl glass p-5">
      <div className="font-medium text-sm">{label}</div>
      <div className="text-xs text-white/50 mt-0.5">{description}</div>
      <div className="mt-3 flex items-center gap-2">
        {prefix && <span className="text-white/50 font-mono">{prefix}</span>}
        <input
          type="number"
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-lg h-10 px-3 font-mono text-base"
        />
        {suffix && <span className="text-white/50 font-mono text-sm">{suffix}</span>}
      </div>
    </div>
  );
}

function ToggleCard({
  label,
  description,
  checked,
  onChange
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        "rounded-xl p-4 text-left border transition",
        checked
          ? "bg-accent/[0.06] border-accent/30"
          : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm">{label}</div>
        <div
          className={cn(
            "w-4 h-4 rounded-full border-2 transition",
            checked ? "bg-accent border-accent shadow-glow" : "border-white/30"
          )}
        />
      </div>
      <div className="text-xs text-white/50 mt-1">{description}</div>
    </button>
  );
}

function BlacklistCard({
  title,
  placeholder,
  items,
  input,
  setInput,
  onAdd,
  onRemove
}: {
  title: string;
  placeholder: string;
  items: string[];
  input: string;
  setInput: (v: string) => void;
  onAdd: () => void;
  onRemove: (v: string) => void;
}) {
  return (
    <div className="rounded-xl glass p-5">
      <div className="font-medium text-sm mb-3">{title}</div>
      <div className="flex gap-2 mb-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onAdd()}
          placeholder={placeholder}
          className="flex-1 bg-white/[0.03] border border-white/[0.06] focus:border-white/20 outline-none rounded-lg h-10 px-3 text-sm"
        />
        <button onClick={onAdd} className="btn-ghost px-3">
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 min-h-[28px]">
        {items.length === 0 && (
          <span className="text-xs text-white/30">No entries yet.</span>
        )}
        {items.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-danger/10 border border-danger/20 text-danger text-xs"
          >
            {v}
            <button onClick={() => onRemove(v)} className="hover:opacity-70">
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
