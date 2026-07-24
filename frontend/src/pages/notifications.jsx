import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  fmtDate,
  getError,
  Button,
  ConfirmModal,
  DataTable,
  EmptyState,
  Pagination,
  StatusBadge,
  Bell,
  Check,
  RefreshCw,
  Search,
  Trash2,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";

const EMPTY_SUMMARY = {
  unread_count: 0,
  read_count: 0,
  total: 0,
  active_alerts: 0,
  resolved_alerts: 0,
  system_events: 0,
};

export function NotificationsPage({ notify, onChanged }) {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [scope, setScope] = useState("all");
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      // O resumo sincroniza os alertas atuais e também cria notificações que
      // estiverem faltando para o usuário conectado.
      const summaryResponse = await api.get("notifications/summary/");
      setSummary({ ...EMPTY_SUMMARY, ...summaryResponse.data });

      const params = new URLSearchParams({ page: String(page) });
      if (filter !== "all") params.set("read", String(filter === "read"));
      if (scope !== "all") params.set("alert_active", String(scope === "current"));
      if (level) params.set("level", level);
      if (search.trim()) params.set("search", search.trim());

      const response = await api.get(`notifications/?${params.toString()}`);
      setRows(unwrap(response.data));
      setCount(response.data?.count ?? unwrap(response.data).length);
    } catch (error) {
      notify(getError(error), "error");
      setRows([]);
      setCount(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filter, scope, level, page, search]); // eslint-disable-line react-hooks/exhaustive-deps

  async function refreshAll() {
    await load();
    await onChanged?.();
    notify("Notificações e alertas atualizados.");
  }

  async function mark(row, read) {
    try {
      await api.post(`notifications/${row.id}/${read ? "mark_read" : "mark_unread"}/`);
      await load();
      await onChanged?.();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function markAll() {
    try {
      const response = await api.post("notifications/mark_all_read/");
      notify(`${response.data.updated} notificação(ões) marcada(s) como lida(s).`);
      await load();
      await onChanged?.();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function deleteConfirmed() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      if (pendingDelete.type === "all-read") {
        const response = await api.delete("notifications/clear_read/");
        notify(`${response.data.deleted} notificação(ões) lida(s) excluída(s).`);
      } else {
        await api.delete(`notifications/${pendingDelete.row.id}/`);
        notify("Notificação excluída permanentemente.");
      }
      setPendingDelete(null);
      await load();
      await onChanged?.();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        actions={(
          <>
            <Button variant="secondary" icon={RefreshCw} onClick={refreshAll}>Atualizar</Button>
            <Button variant="secondary" icon={Check} onClick={markAll} disabled={!summary.unread_count}>
              Marcar todas como lidas
            </Button>
            <Button variant="danger" icon={Trash2} onClick={() => setPendingDelete({ type: "all-read" })} disabled={!summary.read_count}>
              Excluir lidas
            </Button>
          </>
        )}
      />

      <section className="notification-summary-grid" aria-label="Resumo das notificações">
        <div><span>Total</span><strong>{summary.total}</strong><small>Histórico disponível</small></div>
        <div><span>Não lidas</span><strong>{summary.unread_count}</strong><small>Precisam de atenção</small></div>
        <div><span>Situações atuais</span><strong>{summary.active_alerts}</strong><small>Alertas ainda ativos</small></div>
        <div><span>Resolvidas</span><strong>{summary.resolved_alerts}</strong><small>Alertas já normalizados</small></div>
        <div><span>Eventos do sistema</span><strong>{summary.system_events}</strong><small>Operações importantes</small></div>
      </section>

      <div className="filters-bar notification-filters">
        <div className="search-box">
          <Search size={18} />
          <input
            value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            placeholder="Pesquisar nas notificações..."
          />
        </div>
        <select value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1); }}>
          <option value="all">Todas</option>
          <option value="unread">Não lidas</option>
          <option value="read">Lidas</option>
        </select>
        <select value={scope} onChange={(event) => { setScope(event.target.value); setPage(1); }}>
          <option value="all">Todos os tipos</option>
          <option value="current">Situações atuais e eventos</option>
          <option value="resolved">Situações resolvidas</option>
        </select>
        <select value={level} onChange={(event) => { setLevel(event.target.value); setPage(1); }}>
          <option value="">Todos os níveis</option>
          <option value="INFO">Informativo</option>
          <option value="WARNING">Atenção</option>
          <option value="CRITICAL">Crítico</option>
        </select>
      </div>

      <section className="panel">
        {!loading && !rows.length ? (
          <EmptyState
            title={summary.total ? "Nenhuma notificação neste filtro" : "Nenhuma notificação registrada"}
            text={summary.total
              ? "Altere os filtros para consultar outras notificações."
              : "O sistema criará notificações para alertas de estoque, validade, inventários e operações importantes."}
          />
        ) : (
          <DataTable
            loading={loading}
            rows={rows}
            columns={[
              {
                key: "title",
                label: "Notificação",
                render: (row) => (
                  <div className={`notification-table-message ${row.read ? "read" : ""}`}>
                    <strong>{row.title}</strong>
                    <span>{row.message}</span>
                  </div>
                ),
              },
              { key: "reference_display", label: "Referência", render: (row) => row.reference_display || "Sistema" },
              { key: "level", label: "Nível", render: (row) => <StatusBadge value={row.level} label={row.level_display} /> },
              {
                key: "alert_status",
                label: "Situação do aviso",
                render: (row) => row.alert == null
                  ? <StatusBadge value="normal" label="Evento do sistema" />
                  : <StatusBadge value={row.alert_active ? "warning" : "normal"} label={row.alert_active ? "Atual" : "Resolvida"} />,
              },
              { key: "created_at", label: "Data", render: (row) => fmtDate(row.created_at) },
              { key: "status", label: "Leitura", render: (row) => <StatusBadge value={row.read ? "normal" : "warning"} label={row.read ? "Lida" : "Não lida"} /> },
              {
                key: "actions",
                label: "Ações",
                render: (row) => (
                  <div className="row-actions">
                    <button onClick={() => mark(row, !row.read)} title={row.read ? "Marcar como não lida" : "Marcar como lida"}>
                      {row.read ? <Bell size={16} /> : <Check size={16} />}
                    </button>
                    <button
                      className="danger"
                      onClick={() => setPendingDelete({ type: "single", row })}
                      title="Excluir notificação permanentemente"
                      aria-label={`Excluir notificação ${row.title}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ),
              },
            ]}
          />
        )}
        <Pagination page={page} count={count} onChange={setPage} />
      </section>

      {pendingDelete && (
        <ConfirmModal
          title={pendingDelete.type === "all-read" ? "Excluir notificações lidas" : "Excluir notificação"}
          message={pendingDelete.type === "all-read"
            ? "Deseja realmente excluir permanentemente todas as notificações já lidas?"
            : `Deseja realmente excluir a notificação “${pendingDelete.row.title}”?`}
          detail="Esta ação é permanente e não poderá ser desfeita."
          confirmLabel={pendingDelete.type === "all-read" ? "Excluir todas as lidas" : "Excluir notificação"}
          confirmVariant="danger"
          busy={deleting}
          onClose={() => setPendingDelete(null)}
          onConfirm={deleteConfirmed}
        />
      )}
    </>
  );
}
