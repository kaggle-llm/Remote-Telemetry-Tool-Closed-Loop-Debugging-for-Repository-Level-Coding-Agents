(() => {
  const $ = (id) => document.getElementById(id);
  const DEMO_USER = "ios-demo-user";
  let logs = [];

  function notify(message, type = "success") {
    const notice = $("notice");
    notice.textContent = message;
    notice.className = `notice visible ${type}`.trim();
  }

  function renderLogs() {
    const list = $("logs-list");
    $("log-count").textContent = `${logs.length} kayıt`;
    if (!logs.length) {
      list.innerHTML = '<div class="empty-state"><span class="empty-icon">⌁</span><p>Henüz gösterilecek olay yok.</p><span>Simülatörden bir test logu gönder.</span></div>';
      return;
    }
    list.replaceChildren(...logs.map((row) => {
      const card = document.createElement("article");
      card.className = "log-card";
      const level = document.createElement("span");
      level.className = "level";
      level.textContent = row.level;
      const content = document.createElement("div");
      const event = document.createElement("p");
      event.className = "log-event";
      event.textContent = row.event;
      const detail = document.createElement("p");
      detail.className = "log-detail";
      detail.textContent = JSON.stringify(row.detail);
      content.append(event, detail);
      const time = document.createElement("time");
      time.className = "log-time";
      time.dateTime = row.created_at;
      time.textContent = new Date(row.created_at).toLocaleTimeString("tr-TR");
      card.append(level, content, time);
      return card;
    }));
  }

  $("simulate-button").addEventListener("click", () => {
    $("palette").hidden = true;
    $("simulator-message").textContent = "Palette presentation failed · event recorded";
    $("simulator-message").className = "sim-message error";
    logs.unshift({
      id: crypto.randomUUID(),
      user_id: DEMO_USER,
      session_id: crypto.randomUUID().slice(0, 16),
      level: "error",
      event: "highlight_palette_presentation_failed",
      detail: {
        view: "HighlightPaletteView",
        action: "open_palette",
        failure_code: "missing_presentation_context",
        app_version: "web-demo-0.1.0",
        platform: navigator.userAgentData?.platform || navigator.platform || "unknown",
      },
      created_at: new Date().toISOString(),
    });
    renderLogs();
    notify("Test telemetrisi yerel demo günlüğüne eklendi.");
  });

  $("refresh-button").addEventListener("click", () => {
    logs = [];
    renderLogs();
    $("simulator-message").textContent = "Metni seçip highlight düğmesine bas.";
    $("simulator-message").className = "sim-message";
    notify("Demo günlüğü temizlendi.");
  });

  $("palette-trigger").addEventListener("click", () => {
    $("palette").hidden = !$("palette").hidden;
    $("simulator-message").textContent = $("palette").hidden ? "Metni seçip highlight düğmesine bas." : "Palet açıldı.";
    $("simulator-message").className = "sim-message success";
  });
})();
