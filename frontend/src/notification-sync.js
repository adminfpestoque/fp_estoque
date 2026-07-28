let installed = false;
let refreshTimer = null;

function scheduleNotificationRefresh() {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => {
    window.dispatchEvent(new CustomEvent("fp:notifications-changed"));
  }, 300);
}

export function installNotificationSync() {
  if (installed || typeof window === "undefined") return;
  installed = true;

  // As mutações da API já disparam o evento global em shared.jsx. Aqui ficam
  // somente os sinais de retorno à aba, evitando duas consultas por operação.
  window.addEventListener("focus", scheduleNotificationRefresh);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") scheduleNotificationRefresh();
  });
}
