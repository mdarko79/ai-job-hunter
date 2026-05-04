import { cn } from "@/lib/utils";
import type { ApplicationMode } from "@/lib/types";

type StatusEntry = {
  label: string;
  bg: string;
  text: string;
  ring: string;
  dot: string;
};

const statusConfig: Record<string, StatusEntry> = {
  new: {
    label: "New",
    bg: "bg-white/[0.04]",
    text: "text-white/70",
    ring: "ring-white/10",
    dot: "bg-white/40",
  },
  "draft-ready": {
    label: "Draft Ready",
    bg: "bg-electric/10",
    text: "text-electric-glow",
    ring: "ring-electric/20",
    dot: "bg-electric",
  },
  ready: {
    label: "Ready",
    bg: "bg-accent/10",
    text: "text-accent",
    ring: "ring-accent/20",
    dot: "bg-accent",
  },
  "review-needed": {
    label: "Review",
    bg: "bg-warn/10",
    text: "text-warn",
    ring: "ring-warn/20",
    dot: "bg-warn",
  },
  applied: {
    label: "Applied",
    bg: "bg-purple/10",
    text: "text-purple",
    ring: "ring-purple/20",
    dot: "bg-purple",
  },
  "auto-applied": {
    label: "Auto-Applied",
    bg: "bg-purple/10",
    text: "text-purple",
    ring: "ring-purple/20",
    dot: "bg-purple",
  },
  // Application-side statuses
  submitted: {
    label: "Submitted",
    bg: "bg-electric/10",
    text: "text-electric-glow",
    ring: "ring-electric/20",
    dot: "bg-electric",
  },
  viewed: {
    label: "Viewed",
    bg: "bg-electric/10",
    text: "text-electric-glow",
    ring: "ring-electric/20",
    dot: "bg-electric",
  },
  screening: {
    label: "Screening",
    bg: "bg-warn/10",
    text: "text-warn",
    ring: "ring-warn/20",
    dot: "bg-warn",
  },
  interview: {
    label: "Interview",
    bg: "bg-accent/10",
    text: "text-accent",
    ring: "ring-accent/30",
    dot: "bg-accent",
  },
  offer: {
    label: "Offer",
    bg: "bg-accent/15",
    text: "text-accent",
    ring: "ring-accent/40",
    dot: "bg-accent",
  },
  rejected: {
    label: "Rejected",
    bg: "bg-danger/10",
    text: "text-danger",
    ring: "ring-danger/20",
    dot: "bg-danger",
  },
};

const FALLBACK: StatusEntry = {
  label: "Unknown",
  bg: "bg-white/[0.04]",
  text: "text-white/60",
  ring: "ring-white/10",
  dot: "bg-white/30",
};

const modeConfig: Record<string, { label: string; text: string }> = {
  manual: { label: "MANUAL", text: "text-white/60" },
  "semi-auto": { label: "SEMI-AUTO", text: "text-electric-glow" },
  auto: { label: "AUTO", text: "text-accent" },
};

export function StatusBadge({ status }: { status: string }) {
  const c = statusConfig[status] || {
    ...FALLBACK,
    label: status ? prettify(status) : "Unknown",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium ring-1",
        c.bg,
        c.text,
        c.ring
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", c.dot)} />
      {c.label}
    </span>
  );
}

export function ModeBadge({ mode }: { mode: ApplicationMode | string }) {
  const c = modeConfig[mode] || { label: String(mode || "MANUAL").toUpperCase(), text: "text-white/60" };
  return (
    <span className={cn("font-mono text-[10px] tracking-[0.18em] uppercase", c.text)}>
      {c.label}
    </span>
  );
}

function prettify(s: string): string {
  return s.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
