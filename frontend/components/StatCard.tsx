import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: { dir: "up" | "down"; value: string };
  accent?: "default" | "accent" | "electric" | "warn" | "purple";
  sparkline?: number[];
}

const accentMap = {
  default: { ring: "ring-white/10", glow: "from-white/5 to-transparent", text: "text-white" },
  accent: { ring: "ring-accent/20", glow: "from-accent/15 to-transparent", text: "text-accent" },
  electric: {
    ring: "ring-electric/20",
    glow: "from-electric/15 to-transparent",
    text: "text-electric-glow"
  },
  warn: { ring: "ring-warn/20", glow: "from-warn/15 to-transparent", text: "text-warn" },
  purple: { ring: "ring-purple/20", glow: "from-purple/15 to-transparent", text: "text-purple" }
};

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  accent = "default",
  sparkline
}: StatCardProps) {
  const a = accentMap[accent];

  const max = sparkline ? Math.max(...sparkline) : 1;
  const min = sparkline ? Math.min(...sparkline) : 0;
  const range = max - min || 1;

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl glass glass-hover ring-1 p-5 group",
        a.ring
      )}
    >
      <div
        className={cn(
          "absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl bg-gradient-to-br opacity-60 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none",
          a.glow
        )}
      />

      <div className="flex items-center justify-between">
        <div className="label-mono">{label}</div>
        {Icon && <Icon className={cn("w-4 h-4", a.text)} strokeWidth={1.75} />}
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div className={cn("font-serif text-4xl tracking-tight leading-none", a.text)}>
          {value}
        </div>

        {sparkline && (
          <svg viewBox={`0 0 ${sparkline.length * 8} 24`} className="w-20 h-6 opacity-70">
            <polyline
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={a.text}
              points={sparkline
                .map((v, i) => `${i * 8},${24 - ((v - min) / range) * 22}`)
                .join(" ")}
            />
          </svg>
        )}
      </div>

      {trend && (
        <div className="mt-3 flex items-center gap-1.5 text-[11px] font-mono">
          <span className={trend.dir === "up" ? "text-accent" : "text-danger"}>
            {trend.dir === "up" ? "↑" : "↓"} {trend.value}
          </span>
          <span className="text-white/40">vs last week</span>
        </div>
      )}
    </div>
  );
}
