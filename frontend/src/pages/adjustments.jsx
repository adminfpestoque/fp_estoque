
import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  unwrap,
  fmtQty,
  fmtDate,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Pagination,
  AlertTriangle,
  Check,
  Eye,
  History,
  Package,
  Pencil,
  Plus,
  RefreshCw,
  X,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";

const STATUS_LABELS = {
  DRAFT: "Rascunho",
  CONFIRMED: "Confirmado",
  CANCELLED: "Cancelado",
};

const TYPE_LABELS = {
  POSITIVE: "Positivo",
  NEGATIVE: "Negativo",
};

const EMPTY_SUMMARY = {
  total: 0,
  drafts: 0,
  confirmed: 0,
  cancelled: 0,
  positive_quantity: 0,
  negative_quantity: 0,
};

function emptyForm() {
  return {
    id: null,
    product: "",
    lot: "",
    type: "POSITIVE",
    quantity: "1",
    reason: "",
    justification: "",
  };
}

function numberValue(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function AdjustmentsPage({ notify }) {
  const list = useList("adjustments/", { ordering: "-created_at" });
  const [products, setProducts] = useState([]);
  const [lots, setLots] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [form, setForm] = useState(null);
  const [detail, setDetail] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(true);

  async function loadOptions() {
    setLoadingOptions(true);
    try {
      const [productResponse, lotResponse] = await Promise.all([
        api.get("products/?page_size=500&deleted=false&ordering=name"),
        api.get("lots/?page_size=1000&history=false&view=all&ordering=expiration_date"),
      ]);
      setProducts(unwrap(productResponse.data));
      setLots(unwrap(lotResponse.data));
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setLoadingOptions(false);
    }
  }

  async function loadSummary() {
    try {
      const { page, ordering, ...params } = list.params;
      const response = await api.get("adjustments/summary/", { params });
      setSummary({ ...EMPTY_SUMMARY, ...response.data });
    } catch {
      setSummary(EMPTY_SUMMARY);
    }
  }

  useEffect(() => {
    loadOptions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadSummary();
  }, [JSON.stringify(list.params)]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedProduct = useMemo(
    () => products.find((product) => String(product.id) === String(form?.product)),
    [products, form?.product],
  );

  const productLots = useMemo(
    () => lots.filter((lot) => String(lot.product) === String(form?.product)),
    [lots, form?.product],
  );

  const selectedLot = useMemo(
    () => productLots.find((lot) => String(lot.id) === String(form?.lot)),
    [productLots, form?.lot],
  );

  const impact = useMemo(() => {
    if (!form || !selectedProduct) return null;
    const quantity = Math.max(0, numberValue(form.quantity));
    const signal = form.type === "POSITIVE" ? 1 : -1;
    const currentStock = numberValue(selectedProduct.stock);
    const currentLot = selectedLot ? numberValue(selectedLot.quantity) : null;
    return {
      currentStock,
      projectedStock: currentStock + signal * quantity,
      currentLot,
      projectedLot: currentLot == null ? null : currentLot + signal * quantity,
      invalidStock: signal < 0 && quantity > currentStock,
      invalidLot: signal < 0 && currentLot != null && quantity > currentLot,
    };
  }, [form, selectedProduct, selectedLot]);

  function setFilter(name, value) {
    list.setParams((current) => ({ ...current, [name]: value, page: 1 }));
  }

  function clearFilters() {
    list.setParams({ page: 1, ordering: "-created_at" });
  }

  function editAdjustment(row) {
    if (row.status !== "DRAFT") return;
    setForm({
      id: row.id,
      product: String(row.product || ""),
      lot: row.lot ? String(row.lot) : "",
      type: row.type || "POSITIVE",
      quantity: String(row.quantity || 1),
      reason: row.reason || "",
      justification: row.justification || "",
    });
  }

  async function openDetail(row) {
    setBusy(true);
    try {
      const response = await api.get(`adjustments/${row.id}/`);
      setDetail(response.data);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function refreshAfterChange() {
    await Promise.all([list.reload(), loadSummary(), loadOptions()]);
  }

  async function saveAdjustment(confirmNow) {
    if (!form) return;
    if (!form.product || !form.quantity || !form.reason.trim() || !form.justification.trim()) {
      notify("Preencha produto, quantidade, motivo e justificativa.", "error");
      return;
    }
    if (impact?.invalidStock) {
      notify("A quantidade negativa é maior que o estoque atual do produto.", "error");
      return;
    }
    if (impact?.invalidLot) {
      notify("A quantidade negativa é maior que o saldo disponível no lote.", "error");
      return;
    }

    setBusy(true);
    try {
      const payload = {
        product: Number(form.product),
        lot: form.lot ? Number(form.lot) : null,
        type: form.type,
        quantity: form.quantity,
        reason: form.reason.trim(),
        justification: form.justification.trim(),
      };
      const response = form.id
        ? await api.put(`adjustments/${form.id}/`, payload)
        : await api.post("adjustments/", payload);
      let saved = response.data;
      if (confirmNow) {
        const confirmation = await api.post(`adjustments/${saved.id}/confirm/`);
        saved = confirmation.data;
      }
      notify(confirmNow ? "Ajuste confirmado e aplicado ao estoque." : "Ajuste salvo como rascunho.");
      setForm(null);
      await refreshAfterChange();
      if (confirmNow) setDetail(saved);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function executePendingAction() {
    if (!pendingAction) return;
    const { type, row } = pendingAction;
    setBusy(true);
    try {
      const response = await api.post(`adjustments/${row.id}/${type}/`);
      notify(type === "confirm" ? "Ajuste confirmado e aplicado ao estoque." : "Ajuste cancelado e estoque estornado.");
      setPendingAction(null);
      if (detail?.id === row.id) setDetail(response.data);
      await refreshAfterChange();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  const pendingCopy = pendingAction
    ? pendingAction.type === "confirm"
      ? {
          title: "Confirmar ajuste",
          message: `Aplicar o ajuste ${pendingAction.row.number} ao estoque?`,
          detail: "A quantidade do produto e do lote selecionado será alterada imediatamente.",
          label: "Confirmar e aplicar",
          variant: "success",
        }
      : {
          title: "Cancelar ajuste",
          message: `Cancelar o ajuste ${pendingAction.row.number}?`,
          detail: "O sistema criará um estorno automático para devolver o estoque à situação anterior.",
          label: "Cancelar e estornar",
          variant: "danger",
        }
    : null;

  return (
    <>
      <PageHeader
        title="Ajustes de estoque"
        description="Correções autorizadas com rascunho, confirmação, estorno e histórico auditável."
        actions={<Button icon={Plus} onClick={() => setForm(emptyForm())}>Novo ajuste</Button>}
      />

      <div className="adjustment-summary-grid" aria-label="Resumo dos ajustes">
        <div><span>Total</span><strong>{fmtQty(summary.total)}</strong><small>Registros encontrados</small></div>
        <div><span>Rascunhos</span><strong>{fmtQty(summary.drafts)}</strong><small>Aguardando aplicação</small></div>
        <div><span>Confirmados</span><strong>{fmtQty(summary.confirmed)}</strong><small>Aplicados ao estoque</small></div>
        <div><span>Entradas ajustadas</span><strong>+{fmtQty(summary.positive_quantity)}</strong><small>Unidades confirmadas</small></div>
        <div><span>Saídas ajustadas</span><strong>-{fmtQty(summary.negative_quantity)}</strong><small>Unidades confirmadas</small></div>
      </div>

      <div className="filters-bar adjustment-filters">
        <SearchBar
          value={list.params.search || ""}
          onChange={(value) => setFilter("search", value)}
          placeholder="Pesquisar número, produto, motivo..."
        />
        <select value={list.params.status || ""} onChange={(event) => setFilter("status", event.target.value)}>
          <option value="">Todas as situações</option>
          <option value="DRAFT">Rascunhos</option>
          <option value="CONFIRMED">Confirmados</option>
          <option value="CANCELLED">Cancelados</option>
        </select>
        <select value={list.params.type || ""} onChange={(event) => setFilter("type", event.target.value)}>
          <option value="">Todos os tipos</option>
          <option value="POSITIVE">Positivos</option>
          <option value="NEGATIVE">Negativos</option>
        </select>
        <select value={list.params.product || ""} onChange={(event) => setFilter("product", event.target.value)}>
          <option value="">Todos os produtos</option>
          {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
        </select>
        <label className="compact-date-filter"><span>De</span><input type="date" value={list.params.start_date || ""} onChange={(event) => setFilter("start_date", event.target.value)} /></label>
        <label className="compact-date-filter"><span>Até</span><input type="date" value={list.params.end_date || ""} onChange={(event) => setFilter("end_date", event.target.value)} /></label>
        <Button type="button" variant="secondary" icon={RefreshCw} onClick={() => list.reload()}>Atualizar</Button>
        <button type="button" className="link-button adjustment-clear" onClick={clearFilters}>Limpar filtros</button>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          rowClassName={(row) => row.status === "CANCELLED" ? "inactive-row" : ""}
          emptyText="Nenhum ajuste corresponde aos filtros selecionados."
          columns={[
            { key: "number", label: "Número", render: (row) => <button className="table-link" onClick={() => openDetail(row)}>{row.number}</button> },
            { key: "created_at", label: "Data", render: (row) => fmtDate(row.created_at) },
            {
              key: "product",
              label: "Produto",
              render: (row) => <span className="adjustment-product-cell"><strong>{row.product_name}</strong><small>{row.product_code}{row.category_name ? ` • ${row.category_name}` : ""}</small></span>,
            },
            { key: "lot", label: "Lote", render: (row) => row.lot_number || "Sem lote específico" },
            { key: "type", label: "Tipo", render: (row) => <StatusBadge value={row.type} label={TYPE_LABELS[row.type]} /> },
            {
              key: "quantity",
              label: "Quantidade",
              render: (row) => <strong className={row.type === "POSITIVE" ? "adjustment-positive-text" : "adjustment-negative-text"}>{row.type === "POSITIVE" ? "+" : "-"}{fmtQty(row.quantity)}</strong>,
            },
            { key: "reason", label: "Motivo" },
            { key: "status", label: "Situação", render: (row) => <StatusBadge value={row.status} label={STATUS_LABELS[row.status]} /> },
            { key: "user_name", label: "Responsável" },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <div className="row-actions">
                  <button onClick={() => openDetail(row)} title="Ver detalhes" aria-label={`Ver ${row.number}`}><Eye size={16} /></button>
                  {row.status === "DRAFT" && (
                    <>
                      <button onClick={() => editAdjustment(row)} title="Editar rascunho" aria-label={`Editar ${row.number}`}><Pencil size={16} /></button>
                      <button className="success" onClick={() => setPendingAction({ type: "confirm", row })} title="Confirmar ajuste" aria-label={`Confirmar ${row.number}`}><Check size={16} /></button>
                    </>
                  )}
                  {row.status === "CONFIRMED" && <button className="danger" onClick={() => setPendingAction({ type: "cancel", row })} title="Cancelar e estornar" aria-label={`Cancelar ${row.number}`}><X size={16} /></button>}
                  {row.status === "CANCELLED" && <span className="muted-text">Histórico</span>}
                </div>
              ),
            },
          ]}
        />
        <Pagination page={list.params.page || 1} count={list.count} onChange={(page) => list.setParams((current) => ({ ...current, page }))} />
      </section>

      {form && (
        <Modal title={form.id ? "Editar ajuste em rascunho" : "Novo ajuste de estoque"} onClose={() => !busy && setForm(null)} size="lg">
          <div className="adjustment-guidance">
            <AlertTriangle size={21} />
            <div><strong>Use ajustes somente para correções justificadas</strong><p>Compras e saídas normais devem continuar sendo registradas nas respectivas telas.</p></div>
          </div>

          <form className="form-grid cols-2 adjustment-form" onSubmit={(event) => event.preventDefault()}>
            <Field label="Produto" required hint="Inclui produtos ativos e inativos que continuam cadastrados.">
              <select value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value, lot: "" })} disabled={loadingOptions || busy} required>
                <option value="">Selecione um produto</option>
                {products.map((product) => <option key={product.id} value={product.id}>{product.name} — estoque {fmtQty(product.stock)} {product.active ? "" : "(inativo)"}</option>)}
              </select>
            </Field>

            <Field label="Lote" hint="Opcional. Use quando a correção pertence a um lote específico.">
              <select value={form.lot} onChange={(event) => setForm({ ...form, lot: event.target.value })} disabled={!form.product || busy}>
                <option value="">Sem lote específico</option>
                {productLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.number} — saldo {fmtQty(lot.quantity)}{lot.expiration_date ? ` — validade ${fmtDate(lot.expiration_date, false)}` : ""}</option>)}
              </select>
            </Field>

            <Field label="Tipo de ajuste" required>
              <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })} disabled={busy}>
                <option value="POSITIVE">Positivo — acrescentar estoque</option>
                <option value="NEGATIVE">Negativo — retirar estoque</option>
              </select>
            </Field>

            <Field label="Quantidade" required>
              <input type="number" min="1" step="1" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} disabled={busy} required />
            </Field>

            <Field label="Motivo" required hint="Ex.: avaria localizada, erro de contagem ou correção de cadastro.">
              <input list="adjustment-reasons" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} disabled={busy} required />
              <datalist id="adjustment-reasons">
                <option value="Correção de contagem" />
                <option value="Avaria identificada" />
                <option value="Perda não registrada" />
                <option value="Saldo inicial incorreto" />
                <option value="Correção de lote" />
              </datalist>
            </Field>

            <Field label="Justificativa detalhada" required hint="Descreva o que foi conferido e por que o saldo precisa mudar.">
              <textarea value={form.justification} onChange={(event) => setForm({ ...form, justification: event.target.value })} disabled={busy} required />
            </Field>

            <div className={`adjustment-impact full ${impact?.invalidStock || impact?.invalidLot ? "invalid" : ""}`}>
              <div className="adjustment-impact-heading"><Package size={21} /><div><strong>Prévia do impacto</strong><small>O estoque só será alterado quando o ajuste for confirmado.</small></div></div>
              {selectedProduct ? (
                <div className="adjustment-impact-grid">
                  <div><span>Produto</span><strong>{selectedProduct.name}</strong></div>
                  <div><span>Estoque atual</span><strong>{fmtQty(impact.currentStock)}</strong></div>
                  <div><span>Estoque projetado</span><strong>{fmtQty(impact.projectedStock)}</strong></div>
                  {selectedLot && <div><span>Saldo projetado do lote</span><strong>{fmtQty(impact.projectedLot)}</strong></div>}
                </div>
              ) : <p>Selecione um produto para visualizar o impacto.</p>}
              {(impact?.invalidStock || impact?.invalidLot) && <p className="adjustment-impact-error">A quantidade informada deixaria o estoque ou o lote com saldo negativo.</p>}
            </div>

            <div className="form-actions full adjustment-form-actions">
              <Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
              <Button type="button" variant="secondary" icon={History} onClick={() => saveAdjustment(false)} disabled={busy}>{busy ? "Salvando..." : "Salvar rascunho"}</Button>
              <Button type="button" variant="success" icon={Check} onClick={() => saveAdjustment(true)} disabled={busy}>{busy ? "Aplicando..." : "Salvar e confirmar"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {detail && (
        <Modal title={`Ajuste ${detail.number}`} onClose={() => setDetail(null)} size="lg">
          <div className="adjustment-detail">
            <div className="adjustment-detail-head">
              <div><StatusBadge value={detail.status} label={STATUS_LABELS[detail.status]} /><h3>{detail.product_name}</h3><p>{detail.product_code}{detail.category_name ? ` • ${detail.category_name}` : ""}</p></div>
              <StatusBadge value={detail.type} label={`${TYPE_LABELS[detail.type]} ${detail.type === "POSITIVE" ? "+" : "-"}${fmtQty(detail.quantity)}`} />
            </div>

            <div className="adjustment-detail-grid">
              <div><span>Data de criação</span><strong>{fmtDate(detail.created_at)}</strong></div>
              <div><span>Responsável</span><strong>{detail.user_name}</strong></div>
              <div><span>Lote</span><strong>{detail.lot_number || "Sem lote específico"}</strong></div>
              <div><span>Motivo</span><strong>{detail.reason}</strong></div>
              {detail.confirmed_at && <div><span>Confirmado em</span><strong>{fmtDate(detail.confirmed_at)}</strong></div>}
              {detail.cancelled_at && <div><span>Cancelado em</span><strong>{fmtDate(detail.cancelled_at)}</strong></div>}
            </div>

            {detail.movement_previous_stock != null && (
              <div className="adjustment-movement-flow">
                <div><span>Saldo anterior</span><strong>{fmtQty(detail.movement_previous_stock)}</strong></div>
                <span className="adjustment-flow-arrow">→</span>
                <div><span>Saldo após o ajuste</span><strong>{fmtQty(detail.movement_final_stock)}</strong></div>
                {detail.movement_reversed && <StatusBadge value="CANCELLED" label="Movimentação estornada" />}
              </div>
            )}

            <div className="adjustment-justification"><strong>Justificativa registrada</strong><p>{detail.justification}</p></div>

            <div className="form-actions">
              {detail.status === "DRAFT" && (
                <>
                  <Button type="button" variant="secondary" icon={Pencil} onClick={() => { editAdjustment(detail); setDetail(null); }}>Editar rascunho</Button>
                  <Button type="button" variant="success" icon={Check} onClick={() => { setPendingAction({ type: "confirm", row: detail }); setDetail(null); }}>Confirmar ajuste</Button>
                </>
              )}
              {detail.status === "CONFIRMED" && <Button type="button" variant="danger" icon={X} onClick={() => { setPendingAction({ type: "cancel", row: detail }); setDetail(null); }}>Cancelar e estornar</Button>}
              <Button type="button" variant="secondary" onClick={() => setDetail(null)}>Fechar</Button>
            </div>
          </div>
        </Modal>
      )}

      {pendingAction && pendingCopy && (
        <ConfirmModal
          title={pendingCopy.title}
          message={pendingCopy.message}
          detail={pendingCopy.detail}
          confirmLabel={pendingCopy.label}
          confirmVariant={pendingCopy.variant}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={executePendingAction}
        />
      )}
    </>
  );
}
