import {
  React,
  useState,
  fmtDate,
  Logo,
  StatusBadge,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Bell,
  Boxes,
  Check,
  ClipboardCheck,
  FileText,
  Gauge,
  Layers3,
  LogOut,
  Menu,
  Package,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Truck,
  Users,
} from "./shared.jsx";

const menuItems = [
  ["dashboard", Gauge, "Painel", null, "Visão geral do estoque e das vendas em tempo real"],
  ["products", Package, "Produtos", null, "Cadastre, consulte e mantenha o catálogo do estoque."],
  ["categories", Layers3, "Categorias", null, "Organize os produtos por grupos."],
  ["suppliers", Truck, "Fornecedores", null, "Dados cadastrais, contatos e histórico de recebimentos."],
  ["entries", ArrowDownToLine, "Entradas", null, "Recebimentos com lotes, validade, custos e nota fiscal."],
  ["outputs", ArrowUpFromLine, "Saídas", null, "Retiradas internas com controle FEFO e bloqueio de estoque negativo."],
  ["lots", Boxes, "Lotes e validade", null, "Quantidades disponíveis por lote com alertas de vencimento e regra FEFO."],
  ["adjustments", SlidersHorizontal, "Ajustes", "admin", "Correções autorizadas com justificativa obrigatória e histórico auditável."],
  ["inventories", ClipboardCheck, "Inventários", null, "Conte os produtos, identifique sobras e faltas e gere os ajustes com rastreabilidade."],
  ["alerts", AlertTriangle, "Alertas", null, "Estoque mínimo, falta de produtos, validade e divergências."],
  ["notifications", Bell, "Notificações", null, "Acompanhe avisos novos e o histórico de notificações."],
  ["reports", FileText, "Relatórios", null, "Consulte o histórico e gere relatórios em PDF ou planilha (XLSX)."],
  ["users", Users, "Usuários", "admin", "Cadastre usuários e defina diretamente o perfil de acesso de cada pessoa."],
  ["settings", Settings, "Configurações", "admin", "Parâmetros administrativos do estoque e dos alertas."],
];

export function Shell({
  me,
  page,
  setPage,
  onLogout,
  children,
  notifications,
  unreadNotifications = 0,
  onRefreshNotifications,
  onMarkNotificationRead,
  onMarkAllNotificationsRead,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const visibleItems = menuItems.filter((item) => item[3] !== "admin" || me?.permissions?.is_admin);
  const currentPage = menuItems.find(([id]) => id === page);

  function navigate(id) {
    setPage(id);
    setMobileOpen(false);
    setShowNotifications(false);
  }

  return (
    <div className={`shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-top">
          <Logo compact={collapsed} />
          <button className="icon-btn sidebar-collapse" onClick={() => setCollapsed(!collapsed)}><Menu size={20} /></button>
        </div>
        <nav>
          {visibleItems.map(([id, Icon, label]) => (
            <button key={id} className={page === id ? "active" : ""} onClick={() => navigate(id)} title={collapsed ? label : undefined}>
              <Icon size={19} /> {!collapsed && <span>{label}</span>}
            </button>
          ))}
        </nav>
        <button className="sidebar-logout" onClick={onLogout}><LogOut size={19} /> {!collapsed && "Sair"}</button>
      </aside>
      {mobileOpen && <div className="mobile-overlay" onClick={() => setMobileOpen(false)} />}
      <main className="content">
        <header className="topbar">
          <button className="icon-btn mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={22} /></button>
          <div className="topbar-title">
            <h1>{currentPage?.[2] || "FP Estoque"}</h1>
            {currentPage?.[4] && <small>{currentPage[4]}</small>}
          </div>
          <div className="topbar-actions">
            <div className="notification-wrap">
              <button className="icon-btn bell" onClick={() => setShowNotifications(!showNotifications)} aria-label="Abrir notificações">
                <Bell size={20} />
                {unreadNotifications > 0 && <span>{unreadNotifications > 99 ? "99+" : unreadNotifications}</span>}
              </button>
              {showNotifications && (
                <div className="notification-popover">
                  <div className="popover-header">
                    <strong>Notificações</strong>
                    <div className="popover-actions">
                      {unreadNotifications > 0 && (
                        <button onClick={onMarkAllNotificationsRead} title="Marcar todas como lidas"><Check size={15} /></button>
                      )}
                      <button onClick={onRefreshNotifications} title="Atualizar"><RefreshCw size={15} /></button>
                    </div>
                  </div>
                  {notifications?.length ? notifications.map((notification) => (
                    <button
                      type="button"
                      key={notification.id}
                      className={`notification-item ${notification.read ? "read" : "unread"}`}
                      onClick={() => onMarkNotificationRead?.(notification)}
                    >
                      <StatusBadge value={notification.level} label={notification.title} />
                      <p>{notification.message}</p>
                      <small>{fmtDate(notification.created_at)}</small>
                    </button>
                  )) : <p className="muted padded">Nenhuma notificação.</p>}
                  <button className="notification-see-all" onClick={() => navigate("notifications")}>Ver todas as notificações</button>
                </div>
              )}
            </div>
            <div className="user-chip">
              <div>{(me?.profile?.full_name || me?.username || "U").slice(0, 1).toUpperCase()}</div>
              <span>
                <strong>{me?.profile?.full_name || me?.username}</strong>
                <small>{me?.permissions?.role === "ADMIN" ? "Administrador" : "Operador"}</small>
              </span>
            </div>
          </div>
        </header>
        <div className="page-container">{children}</div>
      </main>
    </div>
  );
}

export function PageHeader({ actions }) {
  if (!actions) return null;
  return <div className="page-header page-header-actions-only"><div className="page-actions">{actions}</div></div>;
}

export function MetricCard({ label, value, icon: Icon, tone = "default", detail }) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-icon"><Icon size={21} /></div>
      <div><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
    </div>
  );
}
