export const CASE_STATE_LABELS = {
  reported: "Reported",
  instrumenting: "Preparing instrumentation",
  awaiting_recheck: "Waiting for re-check",
  rechecked: "Re-checked",
  patch_ready: "Waiting for approval",
  approved: "Approved",
  rejected: "Rejected",
  resolved: "Resolved",
  abandoned: "Abandoned",
};

export function caseActions(state) {
  return {
    canReport: state === "awaiting_recheck",
    canApprove: state === "patch_ready",
    canReject: state === "patch_ready",
    isTerminal: state === "resolved" || state === "abandoned",
  };
}

export function formatCaseSummary(item) {
  const state = item?.state || "reported";
  return {
    id: item?.id || "",
    title: item?.title || "(untitled case)",
    state,
    stateLabel: CASE_STATE_LABELS[state] || state,
    updatedAt: item?.updated_at || null,
  };
}

export function formatInstructions(instructions) {
  if (typeof instructions !== "string") return "";
  const trimmed = instructions.trim();
  if (!trimmed) return "The agent has not left instructions for this case yet.";
  return trimmed.slice(0, 8000);
}

export function formatProbes(probes) {
  return (probes || []).map((probe) => ({
    probeId: probe.probe_id || "",
    target: probe.target || "",
    level: probe.level || "warn",
  }));
}
