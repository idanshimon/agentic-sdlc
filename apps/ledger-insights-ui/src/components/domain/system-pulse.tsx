"use client";
/* SystemPulse — the dashboard's HyperFrames hero strip.
 *
 * A thin live band, not a marketing hero: the governed loop as four beats
 * (Agents decide → Gates hold → Humans teach → Policy blocks), each with a real
 * count from the loaded runs + ledger, and a signal that travels the loop.
 * One GSAP timeline, built paused, played once; the travelling pulse is a
 * repeating tween. Reduced motion renders the final state only.
 */
import Link from "next/link";
import { useLayoutEffect, useMemo, useRef } from "react";
import gsap from "gsap";
import { Bot, Hand, GraduationCap, ShieldBan, Radar } from "lucide-react";
import type { LedgerEntry, RunState } from "@/lib/types";
import { decidedBy, stageDecisions, TEACHING_KINDS } from "@/lib/decision-signal";
import { CountUp, prefersReducedMotion } from "@/lib/hyperframe";

export function SystemPulse({ runs, entries }: { runs: RunState[]; entries: LedgerEntry[] }) {
  const beats = useMemo(() => {
    const decisions = stageDecisions(entries);
    return [
      {
        key: "decide", icon: Bot, color: "var(--secondary)", label: "Agents decided",
        value: decisions.filter((e) => decidedBy(e) === "agent").length,
        hint: "autopilot decisions in the ledger", href: "/decisions?actor=agent",
      },
      {
        key: "gate", icon: Hand, color: "var(--warning)", label: "Gates holding",
        value: runs.filter((r) => r.status === "awaiting_gate" || r.status === "paused").length,
        hint: "runs paused for a human", href: "/runs?view=attention",
      },
      {
        key: "teach", icon: GraduationCap, color: "var(--success)", label: "Human calls",
        value: decisions.filter((e) => decidedBy(e) === "human").length + entries.filter((e) => e.runtime_kind && TEACHING_KINDS.has(e.runtime_kind)).length,
        hint: "human decisions + teaching signals", href: "/decisions/lineage",
      },
      {
        key: "block", icon: ShieldBan, color: "var(--danger)", label: "Policy blocks",
        value: runs.filter((r) => r.failure_kind === "policy_block").length,
        hint: "runs refused by a BLOCK rule", href: "/runs?view=failed",
      },
    ];
  }, [runs, entries]);

  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const root = ref.current;
    if (!root || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.from(".sp-beat", { opacity: 0, y: 10, duration: 0.5, stagger: 0.09 })
        .from(".sp-link", { scaleX: 0, transformOrigin: "0% 50%", duration: 0.4, stagger: 0.09 }, 0.15);
      gsap.to(".sp-signal", {
        keyframes: [
          { left: "0%", opacity: 0, duration: 0 },
          { opacity: 1, duration: 0.2 },
          { left: "100%", duration: 3.2, ease: "none" },
          { opacity: 0, duration: 0.2 },
        ],
        repeat: -1,
        repeatDelay: 0.6,
        delay: 0.8,
      });
    }, root);
    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={ref}
      aria-label="Governed loop at a glance"
      className="relative overflow-hidden rounded-lg border border-[var(--border-default)] bg-[var(--surface)] px-4 py-3"
    >
      <div className="pointer-events-none absolute inset-0 opacity-60 [background:radial-gradient(600px_120px_at_15%_0%,color-mix(in_srgb,var(--primary)_10%,transparent),transparent)]" />
      <div className="relative flex items-center gap-3">
        <div className="hidden shrink-0 items-center gap-2 pr-2 text-[11px] text-[var(--text-tertiary)] md:flex">
          <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
          Governed loop
        </div>
        <div className="relative grid flex-1 grid-cols-2 gap-2 md:grid-cols-4 md:gap-0">
          {/* the rail the signal travels on (desktop) */}
          <div className="pointer-events-none absolute left-[12%] right-[12%] top-1/2 hidden h-px -translate-y-1/2 md:block">
            <div className="sp-link h-px w-full bg-[var(--border-default)]" />
            <span className="sp-signal absolute -top-[3px] h-[7px] w-10 -translate-x-1/2 rounded-full bg-[linear-gradient(90deg,transparent,var(--primary),transparent)] opacity-0" />
          </div>
          {beats.map((b) => {
            const Icon = b.icon;
            return (
              <Link
                key={b.key}
                href={b.href}
                title={b.hint}
                className="sp-beat group relative z-10 mx-auto flex w-full max-w-[220px] items-center gap-2.5 rounded-md border border-transparent bg-[var(--surface)] px-2.5 py-1.5 transition-colors hover:border-[var(--border-default)]"
              >
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border"
                  style={{ borderColor: b.color, background: `color-mix(in srgb, ${b.color} var(--tint), transparent)` }}
                >
                  <Icon className="h-4 w-4" style={{ color: b.color }} />
                </span>
                <span className="min-w-0">
                  <span className="tabular block text-lg font-semibold leading-none"><CountUp value={b.value} /></span>
                  <span className="block truncate text-[11px] text-[var(--text-secondary)]">{b.label}</span>
                </span>
              </Link>
            );
          })}
        </div>
        <Link
          href="/mission"
          className="hidden shrink-0 items-center gap-1.5 rounded-md border border-[var(--border-default)] px-2.5 py-1.5 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text)] lg:inline-flex"
        >
          <Radar className="h-3.5 w-3.5 text-[var(--primary)]" /> Mission Control
        </Link>
      </div>
    </section>
  );
}
