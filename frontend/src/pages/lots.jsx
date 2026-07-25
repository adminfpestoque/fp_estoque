
import {
  React,
  fmtMoney,
  fmtQty,
  fmtDate,
  Pagination,
  DataTable,
  StatusBadge,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";

const VIEW_LABELS = {
  available: "Lotes com saldo",
  expiring: "Próximos do vencimento",
  expired: "Vencidos com saldo",
  empty: "Lotes esgotados",
  all: "Todos os lotes cadastrados",
};

export function LotsPage() {
  const list = useList("lots/", { ordering: "expiration_date", view: "available" });

  function changeView(view) {
    list.setParams((current) => ({ ...current, view, page: 1 }));
  }

  return (
    <>
      <PageHeader
        title="Lotes e validade"
        description="Saldos atuais por lote, vinculados somente aos produtos que permanecem cadastrados."
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams((current) => ({ ...current, search, page: 1 }))}
          placeholder="Pesquisar produto, código, lote ou fornecedor..."
        />
        <select value={list.params.view || "available"} onChange={(event) => changeView(event.target.value)}>
          <option value="available">Com saldo disponível</option>
          <option value="expiring">Próximos do vencimento</option>
          <option value="expired">Vencidos com saldo</option>
          <option value="empty">Esgotados</option>
          <option value="all">Todos dos produtos cadastrados</option>
        </select>
      </div>

      <div className="catalog-consistency-note">
        <strong>{VIEW_LABELS[list.params.view || "available"]}</strong>
        <span>Produtos excluídos do cadastro não aparecem nesta área operacional.</span>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          rowClassName={(row) => row.product_active === false ? "inactive-row" : ""}
          emptyText="Nenhum lote operacional corresponde aos filtros selecionados."
          columns={[
            {
              key: "product_name",
              label: "Produto",
              render: (row) => (
                <span>
                  <strong>{row.product_name}</strong>
                  <small className="block">
                    {row.product_code}{row.product_active === false ? " • Produto inativo" : ""}
                  </small>
                </span>
              ),
            },
            { key: "number", label: "Lote" },
            { key: "supplier_name", label: "Fornecedor", render: (row) => row.supplier_name || "-" },
            { key: "quantity", label: "Disponível", render: (row) => fmtQty(row.quantity) },
            { key: "manufacturing_date", label: "Fabricação", render: (row) => fmtDate(row.manufacturing_date, false) },
            { key: "expiration_date", label: "Validade", render: (row) => fmtDate(row.expiration_date, false) },
            { key: "cost_price", label: "Custo", render: (row) => fmtMoney(row.cost_price) },
            {
              key: "status",
              label: "Situação",
              render: (row) => (
                <StatusBadge
                  value={row.status}
                  label={row.status === "EXPIRED" ? "Vencido" : row.status === "EMPTY" ? "Esgotado" : row.status === "INACTIVE" ? "Inativo" : "Disponível"}
                />
              ),
            },
          ]}
        />
        <Pagination
          page={list.params.page || 1}
          count={list.count}
          onChange={(page) => list.setParams((current) => ({ ...current, page }))}
        />
      </section>
    </>
  );
}
