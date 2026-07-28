let installed = false;
let refreshTimer = null;

function scheduleNotificationRefresh() {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => {
    window.dispatchEvent(new CustomEvent("fp:notifications-changed"));
  }, 250);
}

function normalizedPath(url) {
  try {
    return new URL(String(url || ""), window.location.origin)
      .pathname
      .replace(/^\/api\//, "")
      .replace(/^\/+/, "");
  } catch {
    return String(url || "").split("?")[0].replace(/^\/+/, "");
  }
}

function canChangeNotifications(config) {
  const method = String(config?.method || "get").toLowerCase();
  if (["get", "head", "options"].includes(method)) return false;
  const path = normalizedPath(config?.url);
  return /^(entries|outputs|products|lots|adjustments|inventories|alerts|notifications|settings)(?:\/|$)/.test(path);
}

export function installNotificationSync(client) {
  if (installed || typeof window === "undefined") return;
  installed = true;

  client.interceptors.response.use((response) => {
    if (canChangeNotifications(response.config)) scheduleNotificationRefresh();
    return response;
  });

  window.addEventListener("focus", scheduleNotificationRefresh);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") scheduleNotificationRefresh();
  });
}
