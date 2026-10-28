export const CASE_STATE_LABELS = {
  reported: "Bildirildi",
  instrumenting: "Ölçüm hazırlanıyor",
  awaiting_recheck: "Geri bildirim bekleniyor",
  rechecked: "Yeniden kontrol edildi",
  patch_ready: "Onay bekliyor",
  approved: "Onaylandı",
  rejected: "Reddedildi",
  resolved: "Çözüldü",
  abandoned: "Bırakıldı",
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
    title: item?.title || "(başlıksız vaka)",
    state,
    stateLabel: CASE_STATE_LABELS[state] || state,
    updatedAt: item?.updated_at || null,
  };
}

export function formatInstructions(instructions) {
  if (typeof instructions !== "string") return "";
  const trimmed = instructions.trim();
  if (!trimmed) return "Agent bu vaka için henüz talimat bırakmadı.";
  return trimmed.slice(0, 8000);
}

export function formatProbes(probes) {
  return (probes || []).map((probe) => ({
    probeId: probe.probe_id || "",
    target: probe.target || "",
    level: probe.level || "warn",
  }));
}
