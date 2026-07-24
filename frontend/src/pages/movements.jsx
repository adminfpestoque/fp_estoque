import {
  React,
  api,
  fmtMoney,
  fmtQty,
  fmtDate,
  getError,
  Pagination,
  DataTable,
  StatusBadge,
  RefreshCw,
} from "../shared.jsx";
import { SearchBar, useList } from "./listing.jsx";

export function MovementsPage({ me, notify, embedded = false }) {
  const list = useList("movements/");

  async function reverse(row) {
    const reason = window.prompt("Motivo do estorno:", "Correção de movimentação");
    if (!reason) return;
    try {
      await api.post(`movements/${row.id}/reverse/`, { reason });
      notify("Movimentação estornada.");
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <div className={embedded ? "embedded-report-section" : ""}>
      <div className="section-heading">
        <div>
          <h3>Histórico de movimentações</h3>
          <p>Consulte todas as entradas, saídas, ajustes e estornos registrados no estoque.</p>
        </div>
      </div>

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
          placeholder="Produto, lote, documento ou responsável..."
        />
        <input
          type="date"
          aria-label="Data inicial"
          value={list.params.start_date || ""}
          onChange={(event) => list.setParams({ ...list.params, start_date: event.target.value, page: 1 })}
        />
        <input
          type="date"
          aria-label="Data final"
          value={list.params.end_date || ""}
          onChange={(event) => list.setParams({ ...list.params, end_date: event.target.value, page: 1 })}
        />
        <select
          aria-label="Tipo de movimentação"
          value={list.params.type || ""}
          onChange={(event) => list.setParams({ ...list.params, type: event.target.value, page: 1 })}
        >
          <option value="">Todos os tipos</option>
          <option value="ENTRY">Entrada</option>
          <option value="OUTPUT">Saída</option>
          <option value="ADJ_IN">Ajuste positivo</option>
          <option value="ADJ_OUT">Ajuste negativo</option>
          <option value="REV_IN">Estorno positivo</option>
          <option value="REV_OUT">Estorno negativo</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "created_at", label: "Data/hora", render: (row) => fmtDate(row.created_at) },
            { key: "type_display", label: "Tipo", render: (row) => <StatusBadge value={row.type} label={row.type_display} /> },
            { key: "product_name", label: "Produto" },
            { key: "lot_number", label: "Lote" },
            { key: "previous_stock", label: "Anterior", render: (row) => fmtQty(row.previous_stock) },
            { key: "quantity", label: "Movimentada", render: (row) => fmtQty(row.quantity) },
            { key: "final_stock", label: "Final", render: (row) => fmtQty(row.final_stock) },
            { key: "total_value", label: "Valor", render: (row) => fmtMoney(row.total_value) },
            { key: "user_name", label: "Responsável" },
            { key: "document", label: "Documento" },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin && !row.reversed && !String(row.type).startsWith("REV") ? (
                <button className="icon-btn danger" onClick={() => reverse(row)} title="Estornar movimentação">
                  <RefreshCw size={16} />
                </button>
              ) : "-",
            },
          ]}
        />
        <Pagination
          page={list.params.page}
          count={list.count}
          onChange={(page) => list.setParams({ ...list.params, page })}
        />
      </section>
    </div>
  );
}
