"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Search,
  Sparkles,
  Send,
  Shield,
  Building2,
  Settings,
  Activity,
  BookOpen,
  Zap
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cv", label: "My CV", icon: FileText },
  { href: "/jobs", label: "Job Search", icon: Search },
  { href: "/jobs?filter=matched", label: "Matched Jobs", icon: Sparkles },
  { href: "/applications", label: "Applications", icon: Send },
  { href: "/stories", label: "Story Bank", icon: BookOpen },
  { href: "/rules", label: "Auto Apply Rules", icon: Shield },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/logs", label: "Logs", icon: Activity }
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-64 shrink-0 border-r border-white/[0.06] bg-ink-950/40 backdrop-blur-xl flex-col">
      <div className="px-6 pt-7 pb-8">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-electric grid place-items-center shadow-glow">
            <Zap className="w-4 h-4 text-ink-950" strokeWidth={2.5} />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-accent to-electric blur-md opacity-50 -z-10" />
          </div>
          <div className="leading-tight">
            <div className="font-serif italic text-lg text-white">Job Hunter</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">
              AI Agent v0.1
            </div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-3 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active =
            (href === "/" && pathname === "/") ||
            (href !== "/" && pathname.startsWith(href.split("?")[0]) && href.split("?")[0] !== "/");
          return (
            <Link
              key={label}
              href={href}
              className={cn(
                "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200",
                active
                  ? "bg-white/[0.06] text-white border border-white/[0.08]"
                  : "text-white/55 hover:text-white hover:bg-white/[0.03] border border-transparent"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 transition-colors",
                  active ? "text-accent" : "text-white/40 group-hover:text-white/70"
                )}
                strokeWidth={1.75}
              />
              <span className="font-medium">{label}</span>
              {active && <span className="ml-auto w-1 h-1 rounded-full bg-accent shadow-glow" />}
            </Link>
          );
        })}
      </nav>

      <div className="m-3 p-4 rounded-xl glass relative overflow-hidden">
        <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-accent/10 blur-3xl pointer-events-none" />
        <div className="label-mono mb-2">Agent status</div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
          </span>
          <span className="text-sm font-medium">Active</span>
        </div>
        <div className="text-[11px] text-white/40 mt-1 font-mono">3 of 10 daily applies used</div>
      </div>
    </aside>
  );
}
