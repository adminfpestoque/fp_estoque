import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  fmtDate,
  getError,
  Button,
  DataTable,
  StatusBadge,
  Bell,
  Check,
  RefreshCw,
  Trash2,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";

export function NotificationsPage({ notify, onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("unread");

  async function load() {
    setLoading(true);
    try {
      const query = filter === "all" ? "" : `?read=${filter === "read"}`;
      const response = await api.get(`notifications/${query}`);
      setRows(unwrap(response.data));
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

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

  async function clearRead() {
    if (!window.confirm("Remover todas as notificações já lidas?")) return;
    try {
      await api.delete("notifications/clear_read/");
      notify("Notificações lidas removidas.");
      await load();
      await onChanged?.();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <>
      <PageHeader
        actions={(
          <>
            <Button variant="secondary" icon={RefreshCw} onClick={load}>Atualizar</Button>
            <Button variant="secondary" icon={Check} onClick={markAll}>Marcar todas como lidas</Button>
            <Button variant="danger" icon={Trash2} onClick={clearRead}>Limpar lidas</Button>
          </>
        )}
      />
      <div className="filters-bar notification-filters">
        <Bell size={18} />
        <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="unread">Não lidas</option>
          <option value="read">Lidas</option>
          <option value="all">Todas</option>
        </select>
      </div>
      <section className="panel">
        <DataTable
          loading={loading}
          rows={rows}
          emptyText="Nenhuma notificação para o filtro selecionado."
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
            { key: "level", label: "Nível", render: (row) => <StatusBadge value={row.level} label={row.level_display} /> },
            { key: "created_at", label: "Data", render: (row) => fmtDate(row.created_at) },
            { key: "status", label: "Situação", render: (row) => <StatusBadge value={row.read ? "normal" : "warning"} label={row.read ? "Lida" : "Não lida"} /> },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <div className="row-actions">
                  <button onClick={() => mark(row, !row.read)} title={row.read ? "Marcar como não lida" : "Marcar como lida"}>
                    {row.read ? <Bell size={16} /> : <Check size={16} />}
                  </button>
                </div>
              ),
            },
          ]}
        />
      </section>
    </>
  );
}
