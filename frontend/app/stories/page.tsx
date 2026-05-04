"use client";

import { useEffect, useState } from "react";
import { BookOpen, Sparkles, Star, Trash2, Plus, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Story } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const THEMES = [
  { id: "all", label: "All", color: "white/55" },
  { id: "leadership", label: "Leadership", color: "accent" },
  { id: "conflict", label: "Conflict", color: "warn" },
  { id: "failure", label: "Failure", color: "danger" },
  { id: "impact", label: "Impact", color: "electric" },
  { id: "ambiguity", label: "Ambiguity", color: "purple" },
  { id: "technical-decision", label: "Tech decision", color: "accent" },
  { id: "cross-functional", label: "Cross-functional", color: "electric" },
  { id: "mentoring", label: "Mentoring", color: "accent" },
  { id: "customer-impact", label: "Customer impact", color: "warn" },
  { id: "scaling", label: "Scaling", color: "purple" },
];

export default function StoriesPage() {
  const [stories, setStories] = useState<Story[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [showMasterOnly, setShowMasterOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);

  async function fetchStories() {
    setBusy(true);
    try {
      const r = await fetch(`${API}/features/stories`);
      if (r.ok) {
        const data = await r.json();
        setStories(data);
      }
    } catch { /* offline */ }
    finally { setBusy(false); }
  }

  async function generateNew() {
    setGenerating(true);
    try {
      const r = await fetch(`${API}/features/stories/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (r.ok) {
        const data = await r.json();
        if (data.stories?.length) {
          setStories((s) => [...data.stories, ...s]);
        } else {
          alert("No new stories generated. Make sure your CV is uploaded.");
        }
      } else {
        const err = await r.json();
        alert(err.detail || "Failed to generate stories");
      }
    } catch {
      alert("Backend unreachable");
    }
    finally { setGenerating(false); }
  }

  async function toggleMaster(s: Story) {
    try {
      await fetch(`${API}/features/stories/${s.id}/master`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isMaster: !s.isMaster }),
      });
      setStories((arr) => arr.map((x) => x.id === s.id ? { ...x, isMaster: !x.isMaster } : x));
    } catch { /* ignore */ }
  }

  async function deleteStory(s: Story) {
    if (!confirm(`Delete "${s.title}"?`)) return;
    try {
      await fetch(`${API}/features/stories/${s.id}`, { method: "DELETE" });
      setStories((arr) => arr.filter((x) => x.id !== s.id));
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchStories(); }, []);

  const filtered = stories.filter((s) => {
    if (showMasterOnly && !s.isMaster) return false;
    if (filter !== "all" && s.theme !== filter) return false;
    return true;
  });

  const masterCount = stories.filter((s) => s.isMaster).length;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="label-mono mb-2">Story Bank</div>
          <h1 className="font-serif text-4xl tracking-tight">Behavioural stories — STAR+R</h1>
          <p className="text-white/55 mt-1 text-[15px]">
            Mined from your CV against job descriptions you've applied to.
            Promote 5-10 favourites to <span className="text-accent">master stories</span> — they'll
            answer most behavioural questions.
          </p>
        </div>
        <button
          onClick={generateNew}
          disabled={generating}
          className="btn-primary px-5 h-11 inline-flex items-center gap-2"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Generate from CV
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Total stories" value={stories.length} />
        <Stat label="Master stories" value={`${masterCount}${masterCount >= 5 ? " ✓" : " / 5+"}`} accent={masterCount >= 5} />
        <Stat label="Themes covered" value={new Set(stories.map(s => s.theme)).size} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {THEMES.map((t) => (
          <button
            key={t.id}
            onClick={() => setFilter(t.id)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs border transition",
              filter === t.id
                ? "bg-white/10 border-white/20 text-white"
                : "bg-white/[0.02] border-white/5 text-white/55 hover:border-white/10"
            )}
          >
            {t.label}
            {t.id !== "all" && (
              <span className="ml-1.5 font-mono text-white/40">
                {stories.filter(s => s.theme === t.id).length}
              </span>
            )}
          </button>
        ))}
        <button
          onClick={() => setShowMasterOnly(!showMasterOnly)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs border transition inline-flex items-center gap-1.5 ml-auto",
            showMasterOnly
              ? "bg-accent/10 border-accent/30 text-accent"
              : "bg-white/[0.02] border-white/5 text-white/55"
          )}
        >
          <Star className="w-3 h-3" /> Master only
        </button>
      </div>

      {/* Story list */}
      <div className="space-y-4">
        {busy && stories.length === 0 && (
          <div className="text-center text-white/40 py-12">Loading stories...</div>
        )}
        {!busy && filtered.length === 0 && (
          <div className="rounded-2xl glass p-10 text-center">
            <BookOpen className="w-10 h-10 mx-auto text-white/30 mb-4" />
            <h3 className="font-serif text-xl mb-2">No stories yet</h3>
            <p className="text-white/50 text-sm max-w-md mx-auto">
              Generate stories manually with the button above, or enable "Auto-generate stories"
              on the <span className="text-accent">Auto Apply Rules</span> page so they accumulate
              automatically as you apply.
            </p>
          </div>
        )}
        {filtered.map((s) => (
          <StoryCard key={s.id} story={s} onToggleMaster={() => toggleMaster(s)} onDelete={() => deleteStory(s)} />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="rounded-xl glass p-4">
      <div className="label-mono text-[10px] text-white/50">{label}</div>
      <div className={cn("font-mono text-2xl mt-0.5", accent && "text-accent")}>{value}</div>
    </div>
  );
}

function StoryCard({ story, onToggleMaster, onDelete }: {
  story: Story;
  onToggleMaster: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={cn(
      "rounded-2xl glass p-5 transition",
      story.isMaster && "border-accent/30 bg-accent/[0.02]"
    )}>
      <div className="flex items-start gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="px-2 py-0.5 rounded-full bg-white/[0.05] text-[10px] uppercase tracking-wider text-white/60 font-mono">
              {story.theme}
            </span>
            {story.isMaster && (
              <span className="px-2 py-0.5 rounded-full bg-accent/10 text-[10px] uppercase tracking-wider text-accent font-mono inline-flex items-center gap-1">
                <Star className="w-2.5 h-2.5" /> Master
              </span>
            )}
            <span className="text-[10px] text-white/30 font-mono">
              {new Date(story.createdAt).toLocaleDateString()}
            </span>
          </div>
          <h3 className="font-serif text-lg leading-tight">{story.title}</h3>
        </div>
        <button
          onClick={onToggleMaster}
          className={cn(
            "p-2 rounded-lg transition",
            story.isMaster
              ? "bg-accent/10 text-accent"
              : "bg-white/[0.04] text-white/40 hover:text-accent"
          )}
        >
          <Star className="w-4 h-4" fill={story.isMaster ? "currentColor" : "none"} />
        </button>
        <button
          onClick={onDelete}
          className="p-2 rounded-lg bg-white/[0.04] text-white/40 hover:text-danger transition"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2 text-sm">
        <Block letter="S" label="Situation" text={story.situation} />
        <Block letter="T" label="Task" text={story.task} />
        <Block letter="A" label="Action" text={story.action} expanded={expanded} />
        <Block letter="R" label="Result" text={story.result} />
        {story.reflection && <Block letter="+R" label="Reflection" text={story.reflection} />}
      </div>

      {story.answersQuestions && story.answersQuestions.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <div className="label-mono text-[10px] text-white/40 mb-1.5">Answers questions like:</div>
          <div className="flex flex-wrap gap-1.5">
            {story.answersQuestions.slice(0, 4).map((q, i) => (
              <span key={i} className="text-xs px-2 py-1 rounded-md bg-white/[0.03] text-white/60 italic">
                "{q}"
              </span>
            ))}
          </div>
        </div>
      )}

      {!expanded && story.action.length > 200 && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-3 text-xs text-electric hover:underline"
        >
          Show full action…
        </button>
      )}
    </div>
  );
}

function Block({ letter, label, text, expanded }: {
  letter: string;
  label: string;
  text: string;
  expanded?: boolean;
}) {
  const display = !expanded && text.length > 200 ? text.slice(0, 200) + "..." : text;
  return (
    <div className="flex gap-3">
      <div className="w-8 shrink-0">
        <div className="w-7 h-7 rounded-md bg-white/[0.04] border border-white/[0.06] flex items-center justify-center font-mono text-[11px] text-white/70">
          {letter}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="label-mono text-[10px] text-white/40">{label}</div>
        <div className="text-white/80 leading-relaxed">{display}</div>
      </div>
    </div>
  );
}
