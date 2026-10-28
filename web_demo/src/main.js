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
      payload.error = "Supabase tablosu eksik. En güncel supabase_setup.sql dosyasını Supabase SQL Editor'da çalıştırıp yeniden dene.";
    }
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function renderRows(container, rows, kind) {
  container.replaceChildren();
  if (!rows.length) {
    container.textContent = kind === "key" ? "Henüz API key yok." : "AI henüz bir session başlatmadı.";
    return;
  }
  for (const row of rows) {
    const item = document.createElement("div");
    item.className = "key-row";
    const label = document.createElement("span");
    const prefix = kind === "key" ? row.key_prefix : kind === "ingest" ? row.key_prefix : row.session_prefix;
    label.textContent = `${row.name} · ${prefix}… · ${row.revoked_at ? "İptal edildi" : "Aktif"}`;
    const revoke = document.createElement("button");
    revoke.className = "button button-light";
    revoke.textContent = kind === "session" ? "Kapat" : "İptal et";
    revoke.disabled = Boolean(row.revoked_at);
    revoke.addEventListener("click", async () => {
      try {
        const path = kind === "key" ? "keys" : kind === "ingest" ? "ingest-keys" : "sessions";
        await api(`/api/${path}/${row.id}/revoke`, { method: "POST" });
        await loadDashboard();
        notify("Anahtar iptal edildi.", "success");
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
    container.textContent = "Henüz debug vakası yok.";
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
  if (!probes.length) probeBox.textContent = "Aktif probe yok.";
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
  if (!report) { notify("Geri bildirim metni boş olamaz.", "error"); return; }
  try {
    await api(`/api/cases/${state.selectedCaseId}/report`, { method: "POST", body: JSON.stringify({ report }) });
    await loadCases();
    await selectCase(state.selectedCaseId);
    notify("Geri bildirim gönderildi. Vaka yeniden kontrol edildi olarak işaretlendi.", "success");
  } catch (error) { notify(error.message, "error"); }
}

async function decideCase(approved) {
  try {
    await api(`/api/cases/${state.selectedCaseId}/approve`, { method: "POST", body: JSON.stringify({ approved }) });
    await loadCases();
    await selectCase(state.selectedCaseId);
    notify(approved ? "Yama onaylandı. Agent artık logları temizleyebilir." : "Yama reddedildi; vaka yeniden incelemeye dönebilir.", "success");
  } catch (error) { notify(error.message, "error"); }
}

async function createKey() {
  const result = await api("/api/keys", { method: "POST", body: JSON.stringify({ name: $("api-key-name").value.trim() || "Developer agent" }) });
  state.apiKey = result.secret;
  $("new-secret").textContent = result.secret;
  $("secret-panel").hidden = false;
  await loadDashboard();
  notify("API key oluşturuldu. Tam değer yalnızca şimdi gösteriliyor.", "success");
}

async function createIngestKey() {
  const result = await api("/api/ingest-keys", { method: "POST", body: JSON.stringify({ name: $("ingest-key-name").value.trim() || "iOS reader client" }) });
  state.ingestKey = result.secret;
  $("new-ingest-secret").textContent = result.secret;
  $("ingest-secret-panel").hidden = false;
  await loadDashboard();
  notify("Ingest key oluşturuldu. Yalnızca şimdi gösteriliyor.", "success");
}

$("google-login").addEventListener("click", () => { window.location.href = "/api/auth/google"; });
$("create-api-key").addEventListener("click", () => createKey().catch((error) => notify(error.message, "error")));
$("create-ingest-key").addEventListener("click", () => createIngestKey().catch((error) => notify(error.message, "error")));
$("copy-api-key").addEventListener("click", async () => { await navigator.clipboard.writeText(state.apiKey || $("new-secret").textContent); notify("API key panoya kopyalandı.", "success"); });
$("copy-ingest-key").addEventListener("click", async () => { await navigator.clipboard.writeText(state.ingestKey || $("new-ingest-secret").textContent); notify("Ingest key panoya kopyalandı.", "success"); });
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
