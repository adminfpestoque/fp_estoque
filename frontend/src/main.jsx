import React, { useEffect, useState } from "react";
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

function App() {
  const [logged, setLogged] = useState(Boolean(localStorage.getItem("fp_access")));
  const [me, setMe] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [toast, setToast] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const notify = (message, type = "success") => setToast({ message, type });

  function clearSession() {
    localStorage.removeItem("fp_access");
    localStorage.removeItem("fp_refresh");
    setLogged(false);
    setMe(null);
    setNotifications([]);
    setUnreadNotifications(0);
  }

  async function loadMe() {
    try {
      const response = await api.get("users/me/");
      setMe(response.data);
    } catch {
      clearSession();
    }
  }

  async function loadNotifications() {
    try {
      const response = await api.get("notifications/summary/");
      setNotifications(response.data.recent || []);
      setUnreadNotifications(response.data.unread_count || 0);
    } catch (error) {
      if (error?.response?.status === 401) clearSession();
    }
  }

  useEffect(() => {
    if (!logged) return undefined;
    loadMe();
    loadNotifications();
    const timer = window.setInterval(loadNotifications, 60_000);
    return () => window.clearInterval(timer);
  }, [logged]); // eslint-disable-line react-hooks/exhaustive-deps

  async function markNotificationRead(notification) {
    if (notification.read) return;
    try {
      await api.post(`notifications/${notification.id}/mark_read/`);
      await loadNotifications();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function markAllNotificationsRead() {
    try {
      await api.post("notifications/mark_all_read/");
      await loadNotifications();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  if (!logged) return <Login onLogin={() => setLogged(true)} />;
  if (!me) return <div className="app-loading"><Logo /><RefreshCw className="spin" /> Carregando sistema...</div>;

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
    users: <UsersPage notify={notify} />,
    settings: <SettingsPage notify={notify} />,
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
        onRefreshNotifications={loadNotifications}
        onMarkNotificationRead={markNotificationRead}
        onMarkAllNotificationsRead={markAllNotificationsRead}
      >
        {pages[page] || <EmptyState title="Página não encontrada" text="Selecione uma opção no menu." />}
      </Shell>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </>
  );
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
