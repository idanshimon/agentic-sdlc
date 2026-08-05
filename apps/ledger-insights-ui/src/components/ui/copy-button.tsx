"use client";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Small, theme-matched copy-to-clipboard control.
 *
 * Used anywhere an operator needs to lift raw text (event payload JSON,
 * verdict blockers, ids) out of the dashboard and into a ticket, chat, or
 * agent prompt. Falls back to a hidden textarea + execCommand when the async
 * clipboard API is unavailable (non-secure context / older browsers), so the
 * button is never a dead control.
 */
export function CopyButton({
  value,
  label = "Copy",
  className,
  title,
}: {
  value: string;
  label?: string;
  className?: string;
  title?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async (e: React.MouseEvent) => {
    // Inside <summary>, a click would otherwise toggle the <details> open/closed.
    e.preventDefault();
    e.stopPropagation();
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard denied — leave the control in its idle state */
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      title={title ?? "Copy to clipboard"}
      aria-label={title ?? "Copy to clipboard"}
      className={cn(
        "inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded",
        "border border-[var(--border-muted)] text-[var(--text-tertiary)]",
        "hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)] transition-colors",
        className,
      )}
    >
      {copied ? <Check className="h-2.5 w-2.5" /> : <Copy className="h-2.5 w-2.5" />}
      {copied ? "copied" : label}
    </button>
  );
}
