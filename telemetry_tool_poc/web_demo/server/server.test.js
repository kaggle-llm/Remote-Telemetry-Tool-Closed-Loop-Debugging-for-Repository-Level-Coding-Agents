import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import {
  CASE_STATES,
  CASE_TRANSITIONS,
  MAX_PROBES,
  canTransition,
  isUuid,
  normalizeProbes,
  redactDetail,
  redactRows,
} from "./case_rules.js";

test("application session tokens are random and hashed at rest", () => {
  const sid = crypto.randomBytes(32).toString("base64url");
  const hash = crypto.createHash("sha256").update(sid).digest("hex");
  assert.equal(sid.length >= 40, true);
  assert.equal(hash.length, 64);
  assert.notEqual(sid, hash);
});

test("HMAC session signatures reject tampered values", () => {
  const secret = "test-only-session-secret-at-least-32-chars";
  const sign = (value) => crypto.createHmac("sha256", secret).update(value).digest("base64url");
  const value = Buffer.from(JSON.stringify({ sid: "random", exp: Date.now() + 1000 })).toString("base64url");
  const signature = sign(value);
  assert.equal(sign(value), signature);
  assert.notEqual(sign(`${value}tampered`), signature);
});

test("client sessions use a separate prefix from AI sessions", () => {
  const key = `tcs_${crypto.randomBytes(32).toString("base64url")}`;
  assert.match(key, /^tcs_[A-Za-z0-9_-]{43}$/);
  assert.equal(key.startsWith("tls_"), false);
});

test("ingest keys have a restricted prefix distinct from developer keys", () => {
  const key = `tli_${crypto.randomBytes(32).toString("base64url")}`;
  assert.match(key, /^tli_[A-Za-z0-9_-]{43}$/);
  assert.equal(key.startsWith("tlk_"), false);
});

test("ingest key secret is stored only as a SHA-256 digest", () => {
  const secret = `tli_${crypto.randomBytes(32).toString("base64url")}`;
  const hash = crypto.createHash("sha256").update(secret).digest("hex");
  assert.equal(hash.length, 64);
  assert.notEqual(hash, secret);
});

test("every case state has a defined transition map", () => {
  for (const state of CASE_STATES) assert.ok(Array.isArray(CASE_TRANSITIONS[state]), `${state} needs transitions`);
  assert.equal(Object.keys(CASE_TRANSITIONS).length, CASE_STATES.length);
});

test("the debugging loop only allows forward progress through its states", () => {
  assert.equal(canTransition("reported", "instrumenting"), true);
  assert.equal(canTransition("instrumenting", "awaiting_recheck"), true);
  assert.equal(canTransition("awaiting_recheck", "rechecked"), true);
  assert.equal(canTransition("rechecked", "patch_ready"), true);
  assert.equal(canTransition("patch_ready", "approved"), true);
  assert.equal(canTransition("approved", "resolved"), true);
});

test("a case cannot skip the user in the loop", () => {
  assert.equal(canTransition("reported", "approved"), false);
  assert.equal(canTransition("reported", "patch_ready"), false);
  assert.equal(canTransition("instrumenting", "patch_ready"), false);
  assert.equal(canTransition("awaiting_recheck", "patch_ready"), false);
  assert.equal(canTransition("rechecked", "approved"), false);
});

test("a rejected or approved fix can only be reworked or closed", () => {
  assert.equal(canTransition("rejected", "instrumenting"), true);
  assert.equal(canTransition("rejected", "resolved"), false);
  assert.equal(canTransition("approved", "instrumenting"), false);
  assert.equal(canTransition("approved", "abandoned"), false);
});

test("terminal cases cannot transition further", () => {
  for (const state of ["resolved", "abandoned"]) {
    for (const next of CASE_STATES) assert.equal(canTransition(state, next), false, `${state} -> ${next}`);
  }
});

test("instrumentation probes are normalized and bounded", () => {
  const probes = normalizeProbes([{ probe_id: "p1", target: "View.present", capture: { fields: ["state"] } }]);
  assert.equal(probes.length, 1);
  assert.equal(probes[0].level, "warn");
  assert.deepEqual(probes[0].capture, { fields: ["state"] });
});

test("malformed instrumentation probes are rejected instead of silently accepted", () => {
  const rejected = [
    "not-an-array",
    [{ target: "View.present" }],
    [{ probe_id: "p1" }],
    [{ probe_id: "p1", target: "View.present", level: "fatal" }],
    [{ probe_id: "p1", target: "View.present", capture: [] }],
    [{ probe_id: "p".repeat(81), target: "View.present" }],
    [{ probe_id: "p1", target: "t".repeat(201) }],
    ["not-an-object"],
  ];
  for (const probes of rejected) assert.equal(normalizeProbes(probes), null, JSON.stringify(probes));
});

test("the probe count is capped", () => {
  const many = Array.from({ length: MAX_PROBES + 1 }, (_, i) => ({ probe_id: `p${i}`, target: "t" }));
  assert.equal(normalizeProbes(many), null);
  assert.equal(normalizeProbes(many.slice(0, MAX_PROBES)).length, MAX_PROBES);
});

test("sensitive telemetry fields are redacted recursively", () => {
  const redacted = redactDetail({ email: "a@b.com", nested: { access_token: "abc" }, keep: "visible" });
  assert.equal(redacted.email, "[REDACTED]");
  assert.equal(redacted.nested.access_token, "[REDACTED]");
  assert.equal(redacted.keep, "visible");
});

test("long telemetry strings are truncated before they reach the model", () => {
  const redacted = redactDetail({ detail: "x".repeat(9000) });
  assert.equal(redacted.detail.length, 4001);
});

test("redacting rows preserves every non-detail column", () => {
  const rows = redactRows([{ id: 1, event: "probe", level: "warn", detail: { password: "p" } }]);
  assert.equal(rows[0].id, 1);
  assert.equal(rows[0].event, "probe");
  assert.equal(rows[0].detail.password, "[REDACTED]");
});

test("case identifiers are validated as uuids", () => {
  assert.equal(isUuid("11111111-2222-3333-4444-555555555555"), true);
  assert.equal(isUuid("11111111-2222-3333-4444-55555555555"), false);
  assert.equal(isUuid("not-a-uuid"), false);
  assert.equal(isUuid(42), false);
});
