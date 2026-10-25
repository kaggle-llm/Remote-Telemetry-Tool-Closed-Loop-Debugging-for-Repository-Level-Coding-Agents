import "../styles.css";

const $ = (id) => document.getElementById(id);
const state = { user: null, apiKey: null };

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
    label.textContent = `${row.name} · ${kind === "key" ? row.key_prefix : row.session_prefix}… · ${row.revoked_at ? "İptal edildi" : "Aktif"}`;
    const revoke = document.createElement("button");
    revoke.className = "button button-light";
    revoke.textContent = kind === "key" ? "İptal et" : "Kapat";
    revoke.disabled = Boolean(row.revoked_at);
    revoke.addEventListener("click", async () => {
      try {
        await api(`/api/${kind === "key" ? "keys" : "sessions"}/${row.id}/revoke`, { method: "POST" });
        await loadDashboard();
        notify("Anahtar iptal edildi.", "success");
      } catch (error) { notify(error.message, "error"); }
    });
    item.append(label, revoke);
    container.append(item);
  }
}

async function loadDashboard() {
  const [{ user }, keys, sessions] = await Promise.all([api("/api/me"), api("/api/keys"), api("/api/sessions")]);
  state.user = user;
  $("account-email").textContent = user.display_name || user.email;
  showOnly("dashboard-view");
  renderRows($("api-keys"), keys, "key");
  renderRows($("ai-sessions"), sessions, "session");
}

async function createKey() {
  const result = await api("/api/keys", { method: "POST", body: JSON.stringify({ name: $("api-key-name").value.trim() || "Developer agent" }) });
  state.apiKey = result.secret;
  $("new-secret").textContent = result.secret;
  $("secret-panel").hidden = false;
  await loadDashboard();
  notify("API key oluşturuldu. Tam değer yalnızca şimdi gösteriliyor.", "success");
}

$("google-login").addEventListener("click", () => { window.location.href = "/api/auth/google"; });
$("create-api-key").addEventListener("click", () => createKey().catch((error) => notify(error.message, "error")));
$("copy-api-key").addEventListener("click", async () => { await navigator.clipboard.writeText(state.apiKey || $("new-secret").textContent); notify("API key panoya kopyalandı.", "success"); });
$("sign-out").addEventListener("click", async () => {
  window.location.href = "/api/auth/logout";
});

loadDashboard().catch((error) => {
  if (error.message.includes("Sign in") || error.message.includes("Session") || error.message.includes("Invalid session")) showOnly("login-view");
  else { showOnly("login-view"); notify(error.message, "error"); }
});
