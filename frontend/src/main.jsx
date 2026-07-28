import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, EmptyState, getError, Logo, RefreshCw, Toast } from "./shared.jsx";
import { Login } from "./auth.jsx";
import { Shell } from "./layout.jsx";
import { DashboardPage } from "./pages/dashboard.jsx";
import { ProductsPage } from "./pages/products.jsx";
import { SuppliersPage } from "./pages/suppliers.jsx";
import { CategoriesPage } from "./pages/categories.jsx";
import { DocumentPage } from "./pages/documents.jsx";
import { LotsPage } from "./pages/lots.jsx";
import { AdjustmentsPage } from "./pages/adjustments.jsx";
import { InventoriesPage } from "./pages/inventories.jsx";
import { AlertsPage } from "./pages/alerts.jsx";
import { NotificationsPage } from "./pages/notifications.jsx";
import { ReportsPage } from "./pages/reports.jsx";
import { UsersPage } from "./pages/users.jsx";
import { SettingsPage } from "./pages/settings.jsx";
import { installReferenceFallbacks } from "./api-fallback.js";
import { installCreditSaleEnhancements } from "./output-credit.js";
import { installCreditPaymentWorkflow } from "./output-credit-workflow.js";
import { installOutputPaymentStatusConsistency } from "./output-payment-status-consistency.js";
import { installEntryProductColumn } from "./entry-products.js";
import { installMaximumStockRemoval } from "./remove-maximum-stock.js";
import { installProductCostEntryOnly } from "./product-cost-entry-only.js";
import { installProductMinimumStock } from "./product-minimum-stock.js";
import { installProductInlineCreate } from "./product-inline-create.js";
import { installSelectOptionCleanup } from "./select-option-cleanup.js";
import { installNotificationSync } from "./notification-sync.js";
import { installSupplierTableFormat } from "./supplier-table-format.js";
import { installSupplierContactCleanup } from "./supplier-contact-cleanup.js";
import { installSupplierRequiredLabelBridge } from "./supplier-required-label-bridge.js";
import { installSupplierLocationSuggestions } from "./supplier-location-suggestions.js";
import {
  applyAndStorePreferences,
  applyPreferences,
  loadStoredPreferences,
  normalizePreferences,
} from "./preferences.js";

window.__FP_ESTOQUE_RELEASE__ = Object.freeze({
  version: "2026.07.28-final-consistency",
  source: "main",
  features: [
    "minimum-stock-by-unit-or-package",
    "product-create-fields-on-demand",
    "duplicate-select-option-cleanup",
    "supplier-form-and-table-cleanup",
    "supplier-address-and-district-suggestions",
    "entry-output-interface-refinements",
    "credit-due-date-and-payment-status",
    "credit-sale-pending-until-paid",
    "credit-cancelled-payment-status",
    "output-items-by-sale-unit",
    "credit-due-and-overdue-alerts",
    "notification-deduplication-and-navigation",
    "notification-immediate-refresh",
    "notification-failure-backoff",
    "session-recovery-without-forced-logout",
    "entry-cancellation-cost-consistency",
    "render-startup-migrations",
  ],
});
document.documentElement.dataset.fpRelease = window.__FP_ESTOQUE_RELEASE__.version;

installReferenceFallbacks(api);
installCreditSaleEnhancements(api);
installCreditPaymentWorkflow(api);
installOutputPaymentStatusConsistency(api);
installEntryProductColumn(api);
installMaximumStockRemoval(api);
installProductCostEntryOnly(api);
installProductMinimumStock();
installProductInlineCreate();
installSelectOptionCleanup();
installNotificationSync();
installSupplierTableFormat();
installSupplierContactCleanup(api);
installSupplierRequiredLabelBridge();
installSupplierLocationSuggestions();
applyPreferences(loadStoredPreferences());

function notificationDestination(notification) {
  switch (notification?.alert_type) {
    case "LOW_STOCK":
    case "OUT_OF_STOCK":
      return "products";
    case "EXPIRING":
    case "EXPIRED":
      return "lots";
    case "INVENTORY_DIVERGENCE":
      return "inventories";
    case "CREDIT_DUE":
    case "CREDIT_OVERDUE":
      return "outputs";
    default:
      return "notifications";
  }
}

function App() {
  const [logged, setLogged] = useState(Boolean(localStorage.getItem("fp_access")));
  const [me, setMe] = useState(null);
  const [sessionError, setSessionError] = useState("");
  const [page, setPage] = useState("dashboard");
  const [toast, setToast] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const notificationRequestRef = useRef(null);
  const notificationRetryAfterRef = useRef(0);
  const meRetryTimerRef = useRef(null);
  const notify = (message, type = "success") => setToast({ message, type });

  function clearSession() {
    window.clearTimeout(meRetryTimerRef.current);
    localStorage.removeItem("fp_access");
    localStorage.removeItem("fp_refresh");
    notificationRequestRef.current = null;
    notificationRetryAfterRef.current = 0;
    meRetryTimerRef.current = null;
    setLogged(false);
    setMe(null);
    setSessionError("");
    setNotifications([]);
    setUnreadNotifications(0);
  }

  async function loadMe() {
    window.clearTimeout(meRetryTimerRef.current);
    try {
      const response = await api.get("users/me/");
      const preferences = normalizePreferences(response.data.profile || {});
      applyAndStorePreferences(preferences);
      setMe(response.data);
      setSessionError("");
      loadNotifications().catch(() => {});
      return true;
    } catch (error) {
      const status = error?.response?.status;
      if (status === 401 || status === 403) {
        clearSession();
        return false;
      }

      setSessionError("Não foi possível conectar ao servidor agora. A sessão foi preservada e uma nova tentativa será feita automaticamente.");
      meRetryTimerRef.current = window.setTimeout(() => {
        loadMe().catch(() => {});
      }, 15_000);
      return false;
    }
  }

  async function loadNotifications(force = false) {
    if (notificationRequestRef.current) return notificationRequestRef.current;
    if (!force && Date.now() < notificationRetryAfterRef.current) return null;

    const request = api.get("notifications/summary/")
      .then((response) => {
        notificationRetryAfterRef.current = 0;
        setNotifications(response.data.recent || []);
        setUnreadNotifications(response.data.unread_count || 0);
        return response.data;
      })
      .catch((error) => {
        if ([401, 403].includes(error?.response?.status)) {
          clearSession();
        } else {
          // Durante reinício/deploy do backend, evita dezenas de chamadas iguais.
          notificationRetryAfterRef.current = Date.now() + 30_000;
        }
        throw error;
      })
      .finally(() => {
        notificationRequestRef.current = null;
      });

    notificationRequestRef.current = request;
    return request;
  }

  useEffect(() => {
    if (!logged) return undefined;
    loadMe().catch(() => {});
    const timer = window.setInterval(() => {
      loadNotifications().catch(() => {});
    }, 60_000);
    const handleNotificationsChanged = () => {
      loadNotifications().catch(() => {});
    };
    window.addEventListener("fp:notifications-changed", handleNotificationsChanged);
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(meRetryTimerRef.current);
      window.removeEventListener("fp:notifications-changed", handleNotificationsChanged);
    };
  }, [logged]); // eslint-disable-line react-hooks/exhaustive-deps

  async function markNotificationRead(notification) {
    if (notification.read) return notification;
    try {
      const response = await api.post(`notifications/${notification.id}/mark_read/`);
      await loadNotifications(true);
      return response.data;
    } catch (error) {
      notify(getError(error), "error");
      return notification;
    }
  }

  async function openNotification(notification) {
    await markNotificationRead(notification);
    setPage(notificationDestination(notification));
  }

  async function markAllNotificationsRead() {
    try {
      await api.post("notifications/mark_all_read/");
      await loadNotifications(true);
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  if (!logged) return <Login onLogin={() => setLogged(true)} />;
  if (!me) {
    return (
      <div className="app-loading">
        <Logo />
        {!sessionError && <RefreshCw className="spin" />}
        <span>{sessionError || "Carregando sistema..."}</span>
        {sessionError && (
          <button type="button" onClick={() => loadMe().catch(() => {})}>
            Tentar novamente
          </button>
        )}
      </div>
    );
  }

  const pages = {
    dashboard: <DashboardPage />,
    products: <ProductsPage notify={notify} me={me} />,
    categories: <CategoriesPage notify={notify} me={me} />,
    suppliers: <SuppliersPage notify={notify} me={me} />,
    entries: <DocumentPage type="entries" notify={notify} me={me} />,
    outputs: <DocumentPage type="outputs" notify={notify} me={me} />,
    lots: <LotsPage />,
    adjustments: <AdjustmentsPage notify={notify} />,
    inventories: <InventoriesPage me={me} notify={notify} />,
    alerts: <AlertsPage me={me} notify={notify} />,
    notifications: <NotificationsPage notify={notify} onChanged={loadNotifications} />,
    reports: <ReportsPage notify={notify} me={me} />,
    users: <UsersPage notify={notify} me={me} />,
    settings: <SettingsPage notify={notify} me={me} onMeChanged={setMe} />,
  };

  return (
    <>
      <Shell
        me={me}
        page={page}
        setPage={setPage}
        onLogout={clearSession}
        notifications={notifications}
        unreadNotifications={unreadNotifications}
        onRefreshNotifications={() => loadNotifications(true).catch(() => {})}
        onMarkNotificationRead={markNotificationRead}
        onOpenNotification={openNotification}
        onMarkAllNotificationsRead={markAllNotificationsRead}
      >
        {pages[page] || <EmptyState title="Página não encontrada" text="Selecione uma opção no menu." />}
      </Shell>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </>
  );
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
