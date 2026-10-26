export const CASE_STATES = [
  "reported",
  "instrumenting",
  "awaiting_recheck",
  "rechecked",
  "patch_ready",
  "approved",
  "rejected",
  "resolved",
  "abandoned",
];

export const CASE_TRANSITIONS = {
  reported: ["instrumenting", "abandoned"],
  instrumenting: ["awaiting_recheck", "instrumenting", "abandoned"],
  awaiting_recheck: ["rechecked", "instrumenting", "abandoned"],
  rechecked: ["patch_ready", "instrumenting", "abandoned"],
  patch_ready: ["approved", "rejected", "instrumenting", "abandoned"],
  approved: ["resolved"],
  rejected: ["instrumenting", "abandoned"],
  resolved: [],
  abandoned: [],
};

export const SENSITIVE_KEYS = new Set([
  "email", "phone", "token", "password", "authorization", "access_token",
  "refresh_token", "secret", "ssn", "credit_card",
]);

export const MAX_PROBES = 20;

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isUuid = (value) => typeof value === "string" && UUID_PATTERN.test(value);

export function canTransition(from, to) {
  const allowed = CASE_TRANSITIONS[from];
  return Array.isArray(allowed) && allowed.includes(to);
}

export function redactDetail(detail) {
  if (!detail || typeof detail !== "object") return detail;
  const out = Array.isArray(detail) ? [] : {};
  for (const [key, value] of Object.entries(detail)) {
    if (SENSITIVE_KEYS.has(key.toLowerCase())) {
      out[key] = "[REDACTED]";
    } else if (value && typeof value === "object") {
      out[key] = redactDetail(value);
    } else if (typeof value === "string") {
      out[key] = value.length > 4000 ? value.slice(0, 4000) + "…" : value;
    } else {
      out[key] = value;
    }
  }
  return out;
}

export function redactRows(rows) {
  return (rows || []).map((row) => ({ ...row, detail: redactDetail(row.detail) }));
}

export function normalizeProbes(probes) {
  if (!Array.isArray(probes)) return null;
  if (probes.length > MAX_PROBES) return null;
  const cleaned = [];
  for (const probe of probes) {
    if (!probe || typeof probe !== "object" || Array.isArray(probe)) return null;
    const probeId = String(probe.probe_id || "").trim();
    const target = String(probe.target || "").trim();
    const level = String(probe.level || "warn");
    if (!probeId || probeId.length > 80) return null;
    if (!target || target.length > 200) return null;
    if (!["info", "warn", "error"].includes(level)) return null;
    if (probe.capture === undefined || probe.capture === null) {
      cleaned.push({ probe_id: probeId, target, capture: {}, level });
      continue;
    }
    if (typeof probe.capture !== "object" || Array.isArray(probe.capture)) return null;
    cleaned.push({ probe_id: probeId, target, capture: probe.capture, level });
  }
  return cleaned;
}
