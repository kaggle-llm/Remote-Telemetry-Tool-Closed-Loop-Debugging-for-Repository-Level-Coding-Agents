import test from "node:test";
import assert from "node:assert/strict";
import {
  CASE_STATE_LABELS,
  caseActions,
  formatCaseSummary,
  formatInstructions,
  formatProbes,
} from "./case_actions.js";

test("every case state has a human readable label", () => {
  const states = ["reported", "instrumenting", "awaiting_recheck", "rechecked", "patch_ready", "approved", "rejected", "resolved", "abandoned"];
  for (const state of states) assert.ok(CASE_STATE_LABELS[state], `${state} needs a label`);
});

test("feedback is only offered while the case waits for a re-check", () => {
  assert.equal(caseActions("awaiting_recheck").canReport, true);
  assert.equal(caseActions("reported").canReport, false);
  assert.equal(caseActions("rechecked").canReport, false);
  assert.equal(caseActions("patch_ready").canReport, false);
});

test("approval actions are only offered when a patch is ready", () => {
  assert.equal(caseActions("patch_ready").canApprove, true);
  assert.equal(caseActions("patch_ready").canReject, true);
  assert.equal(caseActions("rechecked").canApprove, false);
  assert.equal(caseActions("approved").canApprove, false);
  assert.equal(caseActions("resolved").canReject, false);
});

test("terminal cases are flagged as terminal", () => {
  assert.equal(caseActions("resolved").isTerminal, true);
  assert.equal(caseActions("abandoned").isTerminal, true);
  assert.equal(caseActions("reported").isTerminal, false);
});

test("case summaries fall back to safe defaults", () => {
  const summary = formatCaseSummary({ id: "abc", state: "reported" });
  assert.equal(summary.title, "(başlıksız vaka)");
  assert.equal(summary.stateLabel, "Bildirildi");
  assert.equal(formatCaseSummary({ id: "x", state: "unknown_state" }).stateLabel, "unknown_state");
});

test("instructions are bounded and never empty for the agent view", () => {
  assert.equal(formatInstructions(""), "Agent bu vaka için henüz talimat bırakmadı.");
  assert.equal(formatInstructions("  yama uygula  "), "yama uygula");
  assert.equal(formatInstructions("x".repeat(9000)).length, 8000);
});

test("probes are reduced to display fields", () => {
  const probes = formatProbes([{ probe_id: "p1", target: "View.present", level: "warn", capture: { fields: ["state"] } }]);
  assert.deepEqual(probes, [{ probeId: "p1", target: "View.present", level: "warn" }]);
});
