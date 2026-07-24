import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  fmtMoney,
  fmtQty,
  fmtDate,
  formatMoneyInput,
  toLocalDateTimeInput,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  Pagination,
  DataTable,
  StatusBadge,
  Check,
  Pencil,
  Plus,
  Trash2,
  X,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";

function documentStatus(row) {
  if (row.is_deleted) return ["DELETED", "Excluída"];
  if (row.status === "DRAFT") return [row.status, "Rascunho"];
  if (row.status === "CONFIRMED") return [row.status, "Confirmada"];
  return [row.status, "Cancelada"];
}

export function DocumentPage({ type, notify, me }) {
  const isEntry = type === "entries";
  const list = useList(`${type}/`);
  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [lots, setLots] = useState([]);
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("products/?page_size=500"),
      api.get("suppliers/?page_size=500&active=true"),
      api.get("lots/?page_size=500"),
    ]).then(([productResponse, supplierResponse, lotResponse]) => {
      setProducts(unwrap(productResponse.data));
      setSuppliers(unwrap(supplierResponse.data));
      setLots(unwrap(lotResponse.data));
    });
  }, []);

  const newItem = isEntry
    ? {
        product: "",
        quantity: "1",
        unit_cost: "0,00",
        lot_number: "",
        manufacturing_date: "",
        expiration_date: "",
        notes: "",
      }
    : { product: "", quantity: "1", lot: "", notes: "" };

  function start() {
    setForm(
      isEntry
        ? {
            supplier: "",
            entry_date: toLocalDateTimeInput(),
            invoice_number: "",
            notes: "",
            items: [{ ...newItem }],
          }
        : {
            output_date: toLocalDateTimeInput(),
            reason: "COMMERCIAL",
            notes: "",
            items: [{ ...newItem }],
          },
    );
  }

  function edit(row) {
    if (row.is_deleted) return;
    setForm({
      ...row,
      [isEntry ? "entry_date" : "output_date"]: toLocalDateTimeInput(
        row[isEntry ? "entry_date" : "output_date"],
      ),
      items: row.items.map((item) => ({
        ...item,
        product: item.product || "",
        quantity: String(item.quantity),
        ...(isEntry ? { unit_cost: formatMoneyInput(item.unit_cost) } : {}),
      })),
    });
  }

  function updateItem(index, key, value) {
    setForm({
      ...form,
      items: form.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    });
  }

  async function save(event) {
    event.preventDefault();
    try {
      const dateField = isEntry ? "entry_date" : "output_date";
      const payload = {
        ...form,
        [dateField]: new Date(form[dateField]).toISOString(),
        items: form.items.map((item) => ({
          ...item,
          product: Number(item.product),
          lot: item.lot ? Number(item.lot) : null,
          quantity: String(item.quantity),
          unit_cost: item.unit_cost != null ? String(item.unit_cost) : undefined,
          manufacturing_date: item.manufacturing_date || null,
          expiration_date: item.expiration_date || null,
        })),
      };

      if (form.id) {
        await api.put(`${type}/${form.id}/`, payload);
        notify(
          form.status === "CONFIRMED"
            ? `${isEntry ? "Entrada" : "Saída"} atualizada e estoque recalculado.`
            : `${isEntry ? "Entrada" : "Saída"} atualizada com sucesso.`,
        );
      } else {
        await api.post(`${type}/`, payload);
        notify(`${isEntry ? "Entrada" : "Saída"} salva como rascunho.`);
      }
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function executeAction() {
    if (!pendingAction) return;
    const { row, action } = pendingAction;
    setBusy(true);
    try {
      if (action === "delete") {
        await api.delete(`${type}/${row.id}/`, { data: { reason: "Exclusão solicitada pelo usuário" } });
        notify(
          `${isEntry ? "Entrada" : "Saída"} excluída do uso operacional e mantida no histórico.`,
        );
      } else {
        await api.post(`${type}/${row.id}/${action}/`);
        notify(`Operação realizada em ${row.number}.`);
      }
      setPendingAction(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  const confirmation = pendingAction && (() => {
    const { row, action } = pendingAction;
    if (action === "delete") {
      return {
        title: `Excluir ${isEntry ? "entrada" : "saída"}`,
        message: `Deseja excluir “${row.number}”?`,
        detail:
          "O registro não desaparecerá: continuará no histórico em cinza como Excluído. Se estiver confirmado, o estoque será estornado antes da exclusão lógica.",
        confirmLabel: `Excluir ${isEntry ? "entrada" : "saída"}`,
        confirmVariant: "danger",
      };
    }
    if (action === "confirm") {
      return {
        title: `Confirmar ${isEntry ? "entrada" : "saída"}`,
        message: `Deseja confirmar “${row.number}”?`,
        detail: "A confirmação atualizará o estoque com os itens informados.",
        confirmLabel: "Confirmar",
        confirmVariant: "success",
      };
    }
    return {
      title: `Cancelar ${isEntry ? "entrada" : "saída"}`,
      message: `Deseja cancelar e estornar “${row.number}”?`,
      detail: "O estoque movimentado por este documento será estornado.",
      confirmLabel: "Cancelar e estornar",
      confirmVariant: "danger",
    };
  })();

  const statusFilter = list.params.deleted === "true" ? "DELETED" : list.params.status || "";

  function changeStatusFilter(value) {
    if (value === "DELETED") {
      list.setParams({ ...list.params, status: "", deleted: "true", page: 1 });
    } else {
      const next = { ...list.params, status: value, page: 1 };
      delete next.deleted;
      list.setParams(next);
    }
  }

  return (
    <>
      <PageHeader
        title={isEntry ? "Entradas de estoque" : "Saídas de estoque"}
        description={
          isEntry
            ? "Recebimentos com lotes, validade, custos e nota fiscal."
            : "Retiradas internas com controle FEFO e bloqueio de estoque negativo."
        }
        actions={
          <Button icon={Plus} onClick={start}>
            {isEntry ? "Nova entrada" : "Nova saída"}
          </Button>
        }
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
        />
        <select value={statusFilter} onChange={(event) => changeStatusFilter(event.target.value)}>
          <option value="">Todas as situações</option>
          <option value="DRAFT">Rascunho</option>
          <option value="CONFIRMED">Confirmada</option>
          <option value="CANCELLED">Cancelada</option>
          <option value="DELETED">Excluída</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          rowClassName={(row) => (row.is_deleted ? "row-soft-deleted" : "")}
          columns={[
            {
              key: "number",
              label: "Número",
              render: (row) => (
                <span>
                  <strong>{row.number}</strong>
                  {row.is_deleted && <small className="block">Mantida somente para histórico</small>}
                </span>
              ),
            },
            {
              key: "date",
              label: "Data",
              render: (row) => fmtDate(row[isEntry ? "entry_date" : "output_date"]),
            },
            ...(isEntry
              ? [
                  { key: "supplier_name", label: "Fornecedor" },
                  { key: "invoice_number", label: "Nota fiscal" },
                  {
                    key: "total_value",
                    label: "Valor total",
                    render: (row) => fmtMoney(row.total_value),
                  },
                ]
              : [{ key: "reason_display", label: "Motivo" }]),
            { key: "items", label: "Itens", render: (row) => row.items?.length || 0 },
            {
              key: "status",
              label: "Situação",
              render: (row) => {
                const [value, label] = documentStatus(row);
                return <StatusBadge value={value} label={label} />;
              },
            },
            { key: "user_name", label: "Responsável" },
            {
              key: "actions",
              label: "Ações",
              render: (row) => {
                if (row.is_deleted) return <span className="muted-text">Histórico</span>;
                return (
                  <div className="row-actions">
                    <button
                      onClick={() => edit(row)}
                      title={row.status === "CONFIRMED" ? "Editar e recalcular estoque" : "Editar"}
                    >
                      <Pencil size={16} />
                    </button>
                    {row.status === "DRAFT" && (
                      <button
                        className="success"
                        onClick={() => setPendingAction({ row, action: "confirm" })}
                        title="Confirmar"
                      >
                        <Check size={16} />
                      </button>
                    )}
                    {row.status === "CONFIRMED" && me.permissions.is_admin && (
                      <button
                        className="warning"
                        onClick={() => setPendingAction({ row, action: "cancel" })}
                        title="Cancelar e estornar"
                      >
                        <X size={16} />
                      </button>
                    )}
                    {me.permissions.is_admin && (
                      <button
                        className="danger"
                        onClick={() => setPendingAction({ row, action: "delete" })}
                        title={`Excluir ${isEntry ? "entrada" : "saída"}`}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                );
              },
            },
          ]}
        />
        <Pagination
          page={list.params.page}
          count={list.count}
          onChange={(page) => list.setParams({ ...list.params, page })}
        />
      </section>

      {form && (
        <Modal
          title={`${form.id ? "Editar" : "Nova"} ${isEntry ? "entrada" : "saída"}`}
          onClose={() => setForm(null)}
          size="xl"
        >
          <form onSubmit={save} className="document-form">
            {form.id && form.status === "CONFIRMED" && (
              <div className="document-edit-warning">
                Ao salvar, o sistema estornará a movimentação anterior e aplicará novamente os valores corrigidos.
              </div>
            )}
            {form.id && form.status === "CANCELLED" && (
              <div className="document-edit-warning neutral">
                Este documento está cancelado. A edição atualizará apenas o histórico e não movimentará o estoque.
              </div>
            )}

            <div className="form-grid cols-3">
              {isEntry && (
                <Field label="Fornecedor" required>
                  <select
                    value={form.supplier}
                    onChange={(event) => setForm({ ...form, supplier: event.target.value })}
                    required
                  >
                    <option value="">Selecione</option>
                    {suppliers.map((supplier) => (
                      <option key={supplier.id} value={supplier.id}>
                        {supplier.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              <Field label={isEntry ? "Data da entrada" : "Data da saída"} required>
                <input
                  type="datetime-local"
                  value={form[isEntry ? "entry_date" : "output_date"]}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      [isEntry ? "entry_date" : "output_date"]: event.target.value,
                    })
                  }
                  required
                />
              </Field>
              {isEntry ? (
                <Field label="Número da nota fiscal">
                  <input
                    value={form.invoice_number || ""}
                    onChange={(event) => setForm({ ...form, invoice_number: event.target.value })}
                  />
                </Field>
              ) : (
                <Field label="Motivo" required>
                  <select
                    value={form.reason}
                    onChange={(event) => setForm({ ...form, reason: event.target.value })}
                  >
                    <option value="COMMERCIAL">Retirada para comercialização</option>
                    <option value="TRANSFER">Transferência</option>
                    <option value="LOSS">Perda</option>
                    <option value="DAMAGE">Avaria</option>
                    <option value="EXPIRED">Produto vencido</option>
                    <option value="INTERNAL">Consumo interno</option>
                    <option value="DONATION">Doação</option>
                    <option value="ADJUSTMENT">Ajuste</option>
                    <option value="OTHER">Outros</option>
                  </select>
                </Field>
              )}
              <Field label="Observações">
                <textarea
                  value={form.notes || ""}
                  onChange={(event) => setForm({ ...form, notes: event.target.value })}
                />
              </Field>
            </div>

            <div className="items-editor">
              <div className="items-header">
                <h3>Produtos</h3>
                <Button
                  type="button"
                  variant="secondary"
                  icon={Plus}
                  onClick={() => setForm({ ...form, items: [...form.items, { ...newItem }] })}
                >
                  Adicionar item
                </Button>
              </div>

              {form.items.map((item, index) => (
                <div className="item-row" key={item.id || index}>
                  <Field label="Produto" required>
                    <select
                      value={item.product || ""}
                      onChange={(event) => updateItem(index, "product", event.target.value)}
                      required
                    >
                      <option value="">Selecione</option>
                      {products
                        .filter((product) => product.active || String(product.id) === String(item.product))
                        .map((product) => (
                          <option key={product.id} value={product.id}>
                            {product.name} — estoque {fmtQty(product.stock)}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <Field label="Quantidade" required>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={item.quantity}
                      onChange={(event) => updateItem(index, "quantity", event.target.value)}
                      required
                    />
                  </Field>
                  {isEntry ? (
                    <>
                      <Field label="Custo unitário" required hint="Aceita vírgula ou ponto.">
                        <input
                          type="text"
                          inputMode="decimal"
                          value={item.unit_cost}
                          onChange={(event) => updateItem(index, "unit_cost", event.target.value)}
                          onBlur={() =>
                            updateItem(index, "unit_cost", formatMoneyInput(item.unit_cost))
                          }
                          required
                        />
                      </Field>
                      <Field label="Lote">
                        <input
                          value={item.lot_number || ""}
                          onChange={(event) => updateItem(index, "lot_number", event.target.value)}
                        />
                      </Field>
                      <Field label="Fabricação">
                        <input
                          type="date"
                          value={item.manufacturing_date || ""}
                          onChange={(event) =>
                            updateItem(index, "manufacturing_date", event.target.value)
                          }
                        />
                      </Field>
                      <Field label="Validade">
                        <input
                          type="date"
                          value={item.expiration_date || ""}
                          onChange={(event) =>
                            updateItem(index, "expiration_date", event.target.value)
                          }
                        />
                      </Field>
                    </>
                  ) : (
                    <Field label="Lote (opcional)">
                      <select
                        value={item.lot || ""}
                        onChange={(event) => updateItem(index, "lot", event.target.value)}
                      >
                        <option value="">Automático — FEFO</option>
                        {lots
                          .filter(
                            (lot) =>
                              String(lot.product) === String(item.product) &&
                              (Number(lot.quantity) > 0 || String(lot.id) === String(item.lot)),
                          )
                          .map((lot) => (
                            <option key={lot.id} value={lot.id}>
                              {lot.number} — {fmtQty(lot.quantity)} — {lot.expiration_date || "sem validade"}
                            </option>
                          ))}
                      </select>
                    </Field>
                  )}
                  <button
                    type="button"
                    className="icon-btn danger"
                    disabled={form.items.length === 1}
                    onClick={() =>
                      setForm({
                        ...form,
                        items: form.items.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>

            <div className="form-actions">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>
                Cancelar
              </Button>
              <Button>{form.id ? "Salvar alterações" : "Salvar rascunho"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {confirmation && (
        <ConfirmModal
          {...confirmation}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={executeAction}
        />
      )}
    </>
  );
}
