/**
 * Track B teaching signals — mutation hooks.
 *
 * Each hook posts to /api/feedback/<kind>, which forwards to the matching
 * ledger.<tool> on the MCP server with the bearer token. On success the
 * hook invalidates the decisions + economics + feedback queries so the
 * dashboard reflects the new entry without a full refetch.
 *
 * No optimistic updates — teaching signals matter for compliance, the
 * customer needs to see the server's confirmation before the UI claims
 * the action landed.
 */

"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

async function postFeedback(path: string, body: unknown): Promise<{ id: string }> {
  const res = await fetch(`/api/feedback/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`/api/feedback/${path} ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export function useThumbsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      references_entry_id: string;
      feedback_kind: "thumbs_up" | "thumbs_down";
      actor_id: string;
      rationale?: string;
    }) =>
      postFeedback("thumbs", {
        actor: { kind: "human", id: input.actor_id },
        references_entry_id: input.references_entry_id,
        feedback_kind: input.feedback_kind,
        rationale: input.rationale ?? "",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["economics"] });
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

export function useFlagMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      references_entry_id: string;
      actor_id: string;
      rationale: string;
    }) =>
      postFeedback("flag", {
        actor: { kind: "human", id: input.actor_id },
        references_entry_id: input.references_entry_id,
        rationale: input.rationale,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["economics"] });
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

export function useReplayMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      references_entry_id: string;
      actor_id: string;
      rationale?: string;
    }) =>
      postFeedback("replay", {
        actor: { kind: "human", id: input.actor_id },
        references_entry_id: input.references_entry_id,
        rationale: input.rationale ?? "",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

export function usePauseClassMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      paused_class: string;
      actor_id: string;
      rationale: string;
    }) =>
      postFeedback("pause-class", {
        actor: { kind: "human", id: input.actor_id },
        paused_class: input.paused_class,
        rationale: input.rationale,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}
