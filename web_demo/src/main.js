import "../styles.css";
import { caseActions, formatCaseSummary, formatInstructions, formatProbes } from "./case_actions.js";

const $ = (id) => document.getElementById(id);
const state = { user: null, apiKey: null, ingestKey: null, cases: [], selectedCaseId: null };

function notify(message, kind = "info") {
  const notice = $("notice");
  notice.textContent = message;
  notice.className = `notice visible ${kind}`;
}

function showOnly(id) {
  for (const name of ["login-view", "dashboard-view"]) $(name).hidden = name !== id;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 500 && payload.code === "42P01") {
      payload.error = "The Supabase table is missing. Run the latest supabase_setup.sql file in the Supabase SQL Editor and try again.";
    }
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function renderRows(container, rows, kind) {
  container.replaceChildren();
  if (!rows.length) {
    container.textContent = kind === "key" ? "There is no API key yet." : "The AI has not started a session yet.";
    return;
  }
  for (const row of rows) {
    const item = document.createElement("div");
    item.className = "key-row";
    const label = document.createElement("span");
    const prefix = kind === "key" ? row.key_prefix : kind === "ingest" ? row.key_prefix : row.session_prefix;
    label.textContent = `${row.name} · ${prefix}… · ${row.revoked_at ? "Revoked" : "Active"}`;
    const revoke = document.createElement("button");
    revoke.className = "button button-light";
    revoke.textContent = kind === "session" ? "Close" : "Revoke";
    revoke.disabled = Boolean(row.revoked_at);
    revoke.addEventListener("click", async () => {
      try {
        const path = kind === "key" ? "keys" : kind === "ingest" ? "ingest-keys" : "sessions";
        await api(`/api/${path}/${row.id}/revoke`, { method: "POST" });
        await loadDashboard();
        notify("The key was revoked.", "success");
      } catch (error) { notify(error.message, "error"); }
    });
    item.append(label, revoke);
    container.append(item);
  }
}

async function loadDashboard() {
  const [{ user }, keys, ingestKeys, sessions] = await Promise.all([api("/api/me"), api("/api/keys"), api("/api/ingest-keys"), api("/api/sessions")]);
  state.user = user;
  $("account-email").textContent = user.display_name || user.email;
  showOnly("dashboard-view");
  renderRows($("api-keys"), keys, "key");
  renderRows($("ingest-keys"), ingestKeys, "ingest");
  renderRows($("ai-sessions"), sessions, "session");
  await loadCases();
}

function renderCaseList() {
  const container = $("case-list");
  container.replaceChildren();
  if (!state.cases.length) {
    container.textContent = "There is no debug case yet.";
    return;
  }
  for (const item of state.cases) {
    const summary = formatCaseSummary(item);
    const row = document.createElement("button");
    row.type = "button";
    row.className = "key-row case-row";
    const label = document.createElement("span");
    label.textContent = `${summary.title} · ${summary.stateLabel}`;
    const open = document.createElement("span");
    open.className = "tag";
    open.textContent = summary.state;
    row.append(label, open);
    row.addEventListener("click", () => selectCase(summary.id));
    container.append(row);
  }
}

function renderCaseDetail(detail) {
  const summary = formatCaseSummary(detail.case);
  const actions = caseActions(summary.state);
  $("case-detail").hidden = false;
  $("case-title").textContent = summary.title;
  $("case-state").textContent = summary.stateLabel;
  $("case-instructions").textContent = formatInstructions(detail.case.instructions);
  const probes = formatProbes(detail.probes);
  const probeBox = $("case-probes");
  probeBox.replaceChildren();
  if (!probes.length) probeBox.textContent = "There is no active probe.";
  for (const probe of probes) {
    const item = document.createElement("div");
    item.className = "probe-row";
    item.textContent = `${probe.probeId} → ${probe.target} (${probe.level})`;
    probeBox.append(item);
  }
  $("case-report").value = "";
  $("send-report").disabled = !actions.canReport;
  $("approve-case").disabled = !actions.canApprove;
  $("reject-case").disabled = !actions.canReject;
}

async function loadCases() {
  try {
    state.cases = await api("/api/cases");
    renderCaseList();
    if (state.selectedCaseId) await selectCase(state.selectedCaseId);
  } catch (error) {
    notify(error.message, "error");
  }
}

async function selectCase(caseId) {
  state.selectedCaseId = caseId;
  try {
    const detail = await api(`/api/cases/${caseId}`);
    renderCaseDetail(detail);
  } catch (error) {
    notify(error.message, "error");
  }
}

async function sendReport() {
  const report = $("case-report").value.trim();
  if (!report) { notify("The feedback text cannot be empty.", "error"); return; }
  try {
    await api(`/api/cases/${state.selectedCaseId}/report`, { method: "POST", body: JSON.stringify({ report }) });
    await loadCases();
    await selectCase(state.selectedCaseId);
    notify("Feedback sent. The case is now marked as re-checked.", "success");
  } catch (error) { notify(error.message, "error"); }
}

async function decideCase(approved) {
  try {
    await api(`/api/cases/${state.selectedCaseId}/approve`, { method: "POST", body: JSON.stringify({ approved }) });
    await loadCases();
    await selectCase(state.selectedCaseId);
    notify(approved ? "The patch was approved. The agent can now clean up the logs." : "The patch was rejected; the case can return to review.", "success");
  } catch (error) { notify(error.message, "error"); }
}

async function createKey() {
  const result = await api("/api/keys", { method: "POST", body: JSON.stringify({ name: $("api-key-name").value.trim() || "Developer agent" }) });
  state.apiKey = result.secret;
  $("new-secret").textContent = result.secret;
  $("secret-panel").hidden = false;
  await loadDashboard();
  notify("API key created. The full value is shown only now.", "success");
}

async function createIngestKey() {
  const result = await api("/api/ingest-keys", { method: "POST", body: JSON.stringify({ name: $("ingest-key-name").value.trim() || "iOS reader client" }) });
  state.ingestKey = result.secret;
  $("new-ingest-secret").textContent = result.secret;
  $("ingest-secret-panel").hidden = false;
  await loadDashboard();
  notify("Ingest key created. It is shown only now.", "success");
}

$("google-login").addEventListener("click", () => { window.location.href = "/api/auth/google"; });
$("create-api-key").addEventListener("click", () => createKey().catch((error) => notify(error.message, "error")));
$("create-ingest-key").addEventListener("click", () => createIngestKey().catch((error) => notify(error.message, "error")));
$("copy-api-key").addEventListener("click", async () => { await navigator.clipboard.writeText(state.apiKey || $("new-secret").textContent); notify("The API key was copied to the clipboard.", "success"); });
$("copy-ingest-key").addEventListener("click", async () => { await navigator.clipboard.writeText(state.ingestKey || $("new-ingest-secret").textContent); notify("The ingest key was copied to the clipboard.", "success"); });
$("sign-out").addEventListener("click", async () => {
  window.location.href = "/api/auth/logout";
});
$("refresh-cases").addEventListener("click", () => loadCases());
$("send-report").addEventListener("click", () => sendReport());
$("approve-case").addEventListener("click", () => decideCase(true));
$("reject-case").addEventListener("click", () => decideCase(false));

loadDashboard().catch((error) => {
  if (error.message.includes("Sign in") || error.message.includes("Session") || error.message.includes("Invalid session")) showOnly("login-view");
  else { showOnly("login-view"); notify(error.message, "error"); }
});
