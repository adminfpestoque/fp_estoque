from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado em {path}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def append_once(path, marker, content):
    text = read(path)
    if marker in text:
        return
    write(path, text.rstrip() + "\n\n" + content.strip() + "\n")


write(
    "frontend/src/pages/lots.jsx",
    dedent('''
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
    ''')
)

write(
    "frontend/src/pages/adjustments.jsx",
    dedent('''
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
    ''')
)

replace_once(
    "frontend/src/pages/inventories.jsx",
    '<option value="">Todos os produtos ativos</option>',
    '<option value="">Todos os produtos cadastrados</option>',
)

replace_once(
    "frontend/src/styles.css",
    '@import "./styles/inventory.css";\n',
    '@import "./styles/inventory.css";\n@import "./styles/adjustments.css";\n',
)

write(
    "frontend/src/styles/adjustments.css",
    dedent('''
    .adjustment-summary-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .adjustment-summary-grid > div {
      min-height: 104px;
      padding: 15px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--surface);
      display: grid;
      align-content: center;
      gap: 3px;
    }
    .adjustment-summary-grid span,
    .adjustment-summary-grid small { color: var(--muted); }
    .adjustment-summary-grid span { font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .03em; }
    .adjustment-summary-grid strong { font-size: 25px; line-height: 1.1; }
    .adjustment-summary-grid small { font-size: 12px; }

    .adjustment-filters .compact-date-filter { min-width: 150px; }
    .compact-date-filter { display: grid; gap: 4px; }
    .compact-date-filter > span { color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }
    .compact-date-filter input { min-height: 38px; padding-block: 7px; }
    .adjustment-clear { width: auto; min-width: auto !important; white-space: nowrap; }

    .adjustment-product-cell { display: grid; gap: 3px; min-width: 190px; }
    .adjustment-product-cell small { color: var(--muted); }
    .adjustment-positive-text { color: var(--success); }
    .adjustment-negative-text { color: var(--danger); }

    .adjustment-guidance {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 18px;
      padding: 14px;
      border: 1px solid var(--tone-warning-border, #f2d36b);
      border-radius: 12px;
      background: var(--tone-warning-bg, #fff8dc);
      color: var(--tone-warning-text, #6f5712);
    }
    .adjustment-guidance svg { flex: 0 0 auto; }
    .adjustment-guidance strong { display: block; }
    .adjustment-guidance p { margin: 4px 0 0; color: inherit; line-height: 1.45; font-size: 13px; }

    .adjustment-form textarea { min-height: 112px; }
    .adjustment-impact {
      padding: 15px;
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-subtle);
      display: grid;
      gap: 13px;
    }
    .adjustment-impact.invalid { border-color: var(--danger); background: var(--tone-danger-bg, #fff1f0); }
    .adjustment-impact-heading { display: flex; align-items: flex-start; gap: 10px; }
    .adjustment-impact-heading strong,
    .adjustment-impact-heading small { display: block; }
    .adjustment-impact-heading small { margin-top: 3px; color: var(--muted); }
    .adjustment-impact-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; }
    .adjustment-impact-grid > div {
      padding: 11px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface);
    }
    .adjustment-impact-grid span,
    .adjustment-impact-grid strong { display: block; }
    .adjustment-impact-grid span { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .adjustment-impact-grid strong { margin-top: 5px; }
    .adjustment-impact > p { margin: 0; color: var(--muted); }
    .adjustment-impact-error { color: var(--danger) !important; font-weight: 750; }
    .adjustment-form-actions { padding-top: 4px; }

    .adjustment-detail { display: grid; gap: 18px; }
    .adjustment-detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 15px; border-bottom: 1px solid var(--border); }
    .adjustment-detail-head h3 { margin: 10px 0 3px; }
    .adjustment-detail-head p { margin: 0; color: var(--muted); }
    .adjustment-detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .adjustment-detail-grid > div {
      min-height: 76px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 11px;
      background: var(--surface-subtle);
    }
    .adjustment-detail-grid span,
    .adjustment-detail-grid strong { display: block; }
    .adjustment-detail-grid span { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .adjustment-detail-grid strong { margin-top: 7px; overflow-wrap: anywhere; }
    .adjustment-movement-flow {
      padding: 15px;
      border-radius: 13px;
      background: var(--surface-strong, #111);
      color: var(--surface-strong-text, #fff);
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }
    .adjustment-movement-flow > div { min-width: 150px; }
    .adjustment-movement-flow span,
    .adjustment-movement-flow strong { display: block; }
    .adjustment-movement-flow > div span { color: var(--surface-strong-muted, #d1d5db); font-size: 12px; }
    .adjustment-movement-flow > div strong { margin-top: 4px; font-size: 20px; }
    .adjustment-flow-arrow { color: var(--gold); font-size: 24px; font-weight: 900; }
    .adjustment-justification { padding: 14px; border-left: 4px solid var(--gold); background: var(--surface-subtle); border-radius: 0 11px 11px 0; }
    .adjustment-justification p { margin: 6px 0 0; color: var(--muted); white-space: pre-wrap; line-height: 1.5; }

    .catalog-consistency-note {
      margin: -2px 0 14px;
      padding: 10px 13px;
      border-left: 4px solid var(--gold);
      border-radius: 0 10px 10px 0;
      background: var(--surface-subtle);
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .catalog-consistency-note span { color: var(--muted); font-size: 13px; }

    @media (max-width: 1200px) {
      .adjustment-summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .adjustment-impact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
      .adjustment-summary-grid,
      .adjustment-detail-grid { grid-template-columns: 1fr; }
      .adjustment-filters > * { width: 100% !important; min-width: 100% !important; }
      .adjustment-impact-grid { grid-template-columns: 1fr; }
      .adjustment-detail-head { flex-direction: column; }
      .adjustment-movement-flow { align-items: flex-start; }
      .adjustment-flow-arrow { transform: rotate(90deg); }
      .adjustment-form-actions { flex-direction: column; }
      .adjustment-form-actions .btn { width: 100%; }
    }
    ''')
)

append_once(
    "frontend/src/styles/base.css",
    "/* Paleta semântica refinada para temas escuros */",
    dedent('''
    /* Paleta semântica refinada para temas escuros */
    :root {
      --tone-neutral-bg: #e5e7eb;
      --tone-neutral-text: #374151;
      --tone-neutral-border: #d1d5db;
      --tone-success-bg: #dcfce7;
      --tone-success-text: #166534;
      --tone-success-border: #bbf7d0;
      --tone-warning-bg: #fef3c7;
      --tone-warning-text: #92400e;
      --tone-warning-border: #fde68a;
      --tone-danger-bg: #fee2e2;
      --tone-danger-text: #991b1b;
      --tone-danger-border: #fecaca;
      --row-deleted-bg: #f1f3f5;
      --row-deleted-text: #6b7280;
      --surface-strong: #111111;
      --surface-strong-text: #ffffff;
      --surface-strong-muted: #d1d5db;
      --sticky-surface: rgba(255, 255, 255, .96);
    }

    :root[data-theme="dark"] {
      --page-bg: #0b0c0f;
      --surface: #15171b;
      --surface-subtle: #1d2025;
      --surface-hover: #242117;
      --input-bg: #101216;
      --muted: #9da4af;
      --border: #343942;
      --tone-neutral-bg: #262a31;
      --tone-neutral-text: #c9ced7;
      --tone-neutral-border: #404650;
      --tone-success-bg: #14291d;
      --tone-success-text: #8cdeb0;
      --tone-success-border: #2b5b3e;
      --tone-warning-bg: #302711;
      --tone-warning-text: #f4cf70;
      --tone-warning-border: #66521f;
      --tone-danger-bg: #31191c;
      --tone-danger-text: #ff9b9f;
      --tone-danger-border: #6b3036;
      --row-deleted-bg: #1a1d22;
      --row-deleted-text: #858d99;
      --surface-strong: #0d0f12;
      --surface-strong-text: #f6f7f8;
      --surface-strong-muted: #9da4af;
      --sticky-surface: rgba(21, 23, 27, .96);
    }

    :root[data-theme="contrast"] {
      --tone-neutral-bg: #111111;
      --tone-neutral-text: #ffffff;
      --tone-neutral-border: #ffd400;
      --tone-success-bg: #06160c;
      --tone-success-text: #a2ffc3;
      --tone-success-border: #a2ffc3;
      --tone-warning-bg: #1b1600;
      --tone-warning-text: #ffe56b;
      --tone-warning-border: #ffd400;
      --tone-danger-bg: #1d0707;
      --tone-danger-text: #ff9a9a;
      --tone-danger-border: #ff8080;
      --row-deleted-bg: #0b0b0b;
      --row-deleted-text: #c4c4c4;
      --surface-strong: #000000;
      --surface-strong-text: #ffffff;
      --surface-strong-muted: #f0f0f0;
      --sticky-surface: rgba(0, 0, 0, .97);
    }

    :root[data-theme="dark"] :is(.btn-secondary, .pagination button),
    :root[data-theme="contrast"] :is(.btn-secondary, .pagination button) {
      background: var(--surface-subtle);
      color: var(--text);
      border-color: var(--border);
    }
    :root[data-theme="dark"] .btn-success,
    :root[data-theme="contrast"] .btn-success {
      background: var(--tone-success-bg);
      color: var(--tone-success-text);
      border: 1px solid var(--tone-success-border);
    }
    :root[data-theme="dark"] .btn-danger,
    :root[data-theme="contrast"] .btn-danger {
      background: var(--tone-danger-bg);
      color: var(--tone-danger-text);
      border-color: var(--tone-danger-border);
    }
    :root[data-theme="dark"] .btn-warning,
    :root[data-theme="contrast"] .btn-warning {
      background: var(--tone-warning-bg);
      color: var(--tone-warning-text);
      border-color: var(--tone-warning-border);
    }
    ''')
)

append_once(
    "frontend/src/styles/content.css",
    "/* Correções de contraste para superfícies internas nos temas escuros */",
    dedent('''
    /* Correções de contraste para superfícies internas nos temas escuros */
    :root[data-theme="dark"] .row-soft-deleted,
    :root[data-theme="dark"] .row-soft-deleted:hover,
    :root[data-theme="contrast"] .row-soft-deleted,
    :root[data-theme="contrast"] .row-soft-deleted:hover {
      background: var(--row-deleted-bg) !important;
      color: var(--row-deleted-text) !important;
    }
    :root[data-theme="dark"] .row-soft-deleted strong,
    :root[data-theme="contrast"] .row-soft-deleted strong {
      color: var(--row-deleted-text) !important;
    }
    :root[data-theme="dark"] .row-soft-deleted td,
    :root[data-theme="contrast"] .row-soft-deleted td { opacity: .78; }

    :root[data-theme="dark"] .badge-success,
    :root[data-theme="contrast"] .badge-success { background: var(--tone-success-bg); color: var(--tone-success-text); border: 1px solid var(--tone-success-border); }
    :root[data-theme="dark"] .badge-warning,
    :root[data-theme="contrast"] .badge-warning { background: var(--tone-warning-bg); color: var(--tone-warning-text); border: 1px solid var(--tone-warning-border); }
    :root[data-theme="dark"] .badge-danger,
    :root[data-theme="contrast"] .badge-danger { background: var(--tone-danger-bg); color: var(--tone-danger-text); border: 1px solid var(--tone-danger-border); }
    :root[data-theme="dark"] .badge-neutral,
    :root[data-theme="contrast"] .badge-neutral { background: var(--tone-neutral-bg); color: var(--tone-neutral-text); border: 1px solid var(--tone-neutral-border); }

    :root[data-theme="dark"] :is(.confirmation-danger, .form-error),
    :root[data-theme="contrast"] :is(.confirmation-danger, .form-error) { background: var(--tone-danger-bg); color: var(--tone-danger-text); border-color: var(--tone-danger-border); }
    :root[data-theme="dark"] .confirmation-success,
    :root[data-theme="contrast"] .confirmation-success { background: var(--tone-success-bg); color: var(--tone-success-text); }
    :root[data-theme="dark"] .confirmation-warning,
    :root[data-theme="contrast"] .confirmation-warning { background: var(--tone-warning-bg); color: var(--tone-warning-text); }
    :root[data-theme="dark"] .confirmation-message,
    :root[data-theme="contrast"] .confirmation-message { color: var(--text); }

    :root[data-theme="dark"] :is(.product-placeholder, .summary-cards > div, .report-filters, .dashboard-scope, .document-edit-warning, .document-edit-warning.neutral, .catalog-consistency-note),
    :root[data-theme="contrast"] :is(.product-placeholder, .summary-cards > div, .report-filters, .dashboard-scope, .document-edit-warning, .document-edit-warning.neutral, .catalog-consistency-note) {
      background: var(--surface-subtle) !important;
      color: var(--text) !important;
      border-color: var(--border) !important;
    }
    :root[data-theme="dark"] :is(.dashboard-scope span, .dashboard-scope small, .dashboard-scope strong, .document-edit-warning),
    :root[data-theme="contrast"] :is(.dashboard-scope span, .dashboard-scope small, .dashboard-scope strong, .document-edit-warning) { color: var(--text) !important; }
    :root[data-theme="dark"] .table-link,
    :root[data-theme="contrast"] .table-link { color: var(--gold); }
    :root[data-theme="dark"] .inactive-row,
    :root[data-theme="contrast"] .inactive-row { opacity: .76; }
    :root[data-theme="dark"] .row-actions button.warning,
    :root[data-theme="contrast"] .row-actions button.warning { background: var(--tone-warning-bg); color: var(--tone-warning-text); border-color: var(--tone-warning-border); }
    :root[data-theme="dark"] .row-actions button.success,
    :root[data-theme="contrast"] .row-actions button.success { background: var(--tone-success-bg); color: var(--tone-success-text); border-color: var(--tone-success-border); }
    :root[data-theme="dark"] .row-actions button.danger,
    :root[data-theme="contrast"] .row-actions button.danger { background: var(--tone-danger-bg); color: var(--tone-danger-text); border-color: var(--tone-danger-border); }
    ''')
)

append_once(
    "frontend/src/styles/inventory.css",
    "/* Inventário adaptado aos temas escuros sem superfícies brancas estouradas */",
    dedent('''
    /* Inventário adaptado aos temas escuros sem superfícies brancas estouradas */
    :root[data-theme="dark"] .inventory-progress,
    :root[data-theme="contrast"] .inventory-progress { background: var(--tone-neutral-bg); }

    :root[data-theme="dark"] .inventory-info-box,
    :root[data-theme="contrast"] .inventory-info-box {
      background: var(--tone-warning-bg);
      color: var(--tone-warning-text);
      border-color: var(--tone-warning-border);
    }
    :root[data-theme="dark"] .inventory-info-box :is(p, svg),
    :root[data-theme="contrast"] .inventory-info-box :is(p, svg) { color: var(--tone-warning-text); }

    :root[data-theme="dark"] .inventory-summary-grid > div,
    :root[data-theme="contrast"] .inventory-summary-grid > div {
      background: var(--surface-subtle);
      color: var(--text);
      border-color: var(--border);
    }
    :root[data-theme="dark"] .inventory-summary-grid .positive,
    :root[data-theme="contrast"] .inventory-summary-grid .positive {
      background: var(--tone-success-bg);
      border-color: var(--tone-success-border);
    }
    :root[data-theme="dark"] .inventory-summary-grid .positive strong,
    :root[data-theme="contrast"] .inventory-summary-grid .positive strong { color: var(--tone-success-text) !important; }
    :root[data-theme="dark"] .inventory-summary-grid .negative,
    :root[data-theme="contrast"] .inventory-summary-grid .negative {
      background: var(--tone-danger-bg);
      border-color: var(--tone-danger-border);
    }
    :root[data-theme="dark"] .inventory-summary-grid .negative strong,
    :root[data-theme="contrast"] .inventory-summary-grid .negative strong { color: var(--tone-danger-text) !important; }

    :root[data-theme="dark"] .inventory-progress-wide,
    :root[data-theme="contrast"] .inventory-progress-wide {
      background: var(--surface-strong);
      color: var(--surface-strong-text);
      border: 1px solid var(--border);
    }
    :root[data-theme="dark"] .inventory-progress-wide span,
    :root[data-theme="contrast"] .inventory-progress-wide span { color: var(--surface-strong-muted); }

    :root[data-theme="dark"] .inventory-checklist .ok,
    :root[data-theme="contrast"] .inventory-checklist .ok { background: var(--tone-success-bg); color: var(--tone-success-text); border: 1px solid var(--tone-success-border); }
    :root[data-theme="dark"] .inventory-checklist .pending,
    :root[data-theme="contrast"] .inventory-checklist .pending { background: var(--tone-warning-bg); color: var(--tone-warning-text); border: 1px solid var(--tone-warning-border); }

    :root[data-theme="dark"] .inventory-items-toolbar,
    :root[data-theme="contrast"] .inventory-items-toolbar { background: var(--surface-subtle); }
    :root[data-theme="dark"] .inventory-table th,
    :root[data-theme="contrast"] .inventory-table th { background: var(--surface-subtle) !important; }
    :root[data-theme="dark"] .inventory-table td,
    :root[data-theme="contrast"] .inventory-table td { background: var(--surface) !important; }
    :root[data-theme="dark"] .inventory-row-divergence td,
    :root[data-theme="contrast"] .inventory-row-divergence td { background: var(--tone-warning-bg) !important; }
    :root[data-theme="dark"] .inventory-reason.invalid,
    :root[data-theme="contrast"] .inventory-reason.invalid { background: var(--tone-danger-bg); border-color: var(--tone-danger-border); }
    :root[data-theme="dark"] .inventory-actions,
    :root[data-theme="contrast"] .inventory-actions { background: var(--sticky-surface); }
    ''')
)
