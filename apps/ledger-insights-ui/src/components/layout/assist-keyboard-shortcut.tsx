"use client";
import { useEffect } from "react";
import { useAssist } from "@/lib/assist/context";

/**
 * Global ⌘K / Ctrl+K shortcut to toggle the AssistantPanel.
 * Mounted once at the root layout; reads/writes state via useAssist().
 */
export function AssistKeyboardShortcut() {
  const { open, setOpen } = useAssist();
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        // Skip if user is in an input where ⌘K means "delete-line" or
        // similar — but for our app, a top-level shortcut is fine.
        const target = e.target as HTMLElement | null;
        const tag = target?.tagName?.toLowerCase();
        if (tag === "input" || tag === "textarea") return;
        e.preventDefault();
        setOpen(!open);
      }
      if (e.key === "Escape" && open) {
        // Sheet handles Escape natively, so this is a no-op fallback.
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, setOpen]);
  return null;
}
