import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  unwrap,
  fmtMoney,
  fmtQty,
  fmtDate,
  getError,
  Button,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Pagination,
  Check,
  ClipboardCheck,
  Eye,
  Plus,
  RefreshCw,
  Search,
  X,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";

const STATUS_LABELS = {
  OPEN: "Em andamento",
  WAITING: "Aguardando confirmação",
  DONE: "Concluído",
  CANCELLED: "Cancelado",
};

const ITEM_FILTERS = {
  all: "Todos",
  pending: "Não contados",
  divergences: "Com divergência",
  counted: "Conferidos",
};

function buildDrafts(items = []) {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      {
        counted: Boolean(item.counted),
        counted_quantity: String(item.counted_quantity ?? item.system_quantity ?? 0),
        justification: item.justification || "",
      },
    ]),
  );
}

function numberValue(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function InventoriesPage({ me, notify }) {
  const list = useList("inventories/", { ordering: "-started_at" });
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(null);
  const [detail, setDetail] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [itemSearch, setItemSearch] = useState("");
  const [itemFilter, setItemFilter] = useState("all");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get("categories/?page_size=200&ordering=name")
      .then((response) => setCategories(unwrap(response.data)))
      .catch(() => setCategories([]));
  }, []);

  function setListFilter(name, value) {
    list.setParams((current) => ({ ...current, page: 1, [name]: value }));
  }

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await api.post("inventories/", {
        category: form.category || null,
        notes: form.notes.trim(),
        populate: true,
      });
      notify("Inventário iniciado. Registre a contagem física dos produtos.");
      setForm(null);
      list.reload();
      await openInventory(response.data.id);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function openInventory(id) {
    setBusy(true);
    try {
      const response = await api.get(`inventories/${id}/`);
      setDetail(response.data);
      setDrafts(buildDrafts(response.data.items));
      setItemSearch("");
      setItemFilter("all");
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  function updateDraft(itemId, patch) {
    setDrafts((current) => ({
      ...current,
      [itemId]: { ...current[itemId], ...patch },
    }));
  }

  function markAllAsCounted() {
    setDrafts((current) => {
      const next = { ...current };
      for (const item of detail.items) {
        next[item.id] = {
          ...next[item.id],
          counted: true,
          counted_quantity: String(item.system_quantity),
        };
      }
      return next;
    });
  }

  function countPayload() {
    return detail.items
      .filter((item) => drafts[item.id]?.counted)
      .map((item) => ({
        product: item.product,
        counted_quantity: drafts[item.id].counted_quantity,
        justification: drafts[item.id].justification.trim(),
      }));
  }

  async function saveCounts(showMessage = true) {
    const items = countPayload();
    if (!items.length) {
      notify("Marque pelo menos um produto como conferido.", "error");
      return null;
    }

    setBusy(true);
    try {
      const response = await api.post(`inventories/${detail.id}/bulk_count/`, { items });
      setDetail(response.data);
      setDrafts(buildDrafts(response.data.items));
      if (showMessage) notify("Contagens salvas com sucesso.");
      list.reload();
      return response.data;
    } catch (error) {
      notify(getError(error), "error");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitInventory() {
    const saved = await saveCounts(false);
    if (!saved) return;
    setBusy(true);
    try {
      const response = await api.post(`inventories/${detail.id}/submit/`);
      setDetail(response.data);
      setDrafts(buildDrafts(response.data.items));
      notify("Inventário enviado para confirmação do administrador.");
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function inventoryAction(action, successMessage, payload = {}) {
    setBusy(true);
    try {
      const response = await api.post(`inventories/${detail.id}/${action}/`, payload);
      setDetail(response.data);
      setDrafts(buildDrafts(response.data.items));
      notify(successMessage);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function cancelInventory() {
    const reason = window.prompt("Informe o motivo do cancelamento:", "");
    if (reason === null) return;
    await inventoryAction("cancel", "Inventário cancelado.", { reason });
  }

  const localSummary = useMemo(() => {
    if (!detail) return null;
    let counted = 0;
    let positive = 0;
    let negative = 0;
    let value = 0;
    let missingJustification = 0;

    for (const item of detail.items) {
      const draft = drafts[item.id];
      if (!draft?.counted) continue;
      counted += 1;
      const difference = numberValue(draft.counted_quantity) - numberValue(item.system_quantity);
      value += difference * numberValue(item.unit_cost);
      if (difference > 0) positive += 1;
      if (difference < 0) negative += 1;
      if (difference !== 0 && !draft.justification.trim()) missingJustification += 1;
    }

    return {
      total: detail.items.length,
      counted,
      pending: detail.items.length - counted,
      divergences: positive + negative,
      positive,
      negative,
      value,
      missingJustification,
      progress: detail.items.length ? (counted / detail.items.length) * 100 : 0,
    };
  }, [detail, drafts]);

  const visibleItems = useMemo(() => {
    if (!detail) return [];
    const query = itemSearch.trim().toLowerCase();
    return detail.items.filter((item) => {
      const draft = drafts[item.id];
      const difference = numberValue(draft?.counted_quantity) - numberValue(item.system_quantity);
      const matchesSearch =
        !query ||
        item.product_name.toLowerCase().includes(query) ||
        item.product_code.toLowerCase().includes(query) ||
        (item.category_name || "").toLowerCase().includes(query);
      const matchesFilter =
        itemFilter === "all" ||
        (itemFilter === "pending" && !draft?.counted) ||
        (itemFilter === "counted" && draft?.counted) ||
        (itemFilter === "divergences" && draft?.counted && difference !== 0);
      return matchesSearch && matchesFilter;
    });
  }, [detail, drafts, itemSearch, itemFilter]);

  const editable = detail?.status === "OPEN";
  const canSubmit =
    editable &&
    localSummary?.pending === 0 &&
    localSummary?.missingJustification === 0 &&
    localSummary?.total > 0;

  return (
    <>
      <PageHeader
        title="Conferência física de estoque"
        description="Conte os produtos, identifique sobras e faltas e gere os ajustes com rastreabilidade."
        actions={
          <Button icon={Plus} onClick={() => setForm({ category: "", notes: "" })}>
            Novo inventário
          </Button>
        }
      />

      <div className="filters-bar inventory-list-filters">
        <SearchBar
          value={list.params.search || ""}
          onChange={(value) => setListFilter("search", value)}
          placeholder="Pesquisar número, produto ou observação..."
        />
        <select
          value={list.params.status || ""}
          onChange={(event) => setListFilter("status", event.target.value)}
        >
          <option value="">Todas as situações</option>
          <option value="OPEN">Em andamento</option>
          <option value="WAITING">Aguardando confirmação</option>
          <option value="DONE">Concluído</option>
          <option value="CANCELLED">Cancelado</option>
        </select>
        <select
          value={list.params.category || ""}
          onChange={(event) => setListFilter("category", event.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>{category.name}</option>
          ))}
        </select>
        <Button
          type="button"
          variant="secondary"
          icon={RefreshCw}
          onClick={() => list.reload()}
        >
          Atualizar
        </Button>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          emptyText="Inicie um inventário para começar a conferência física do estoque."
          columns={[
            {
              key: "number",
              label: "Inventário",
              render: (row) => (
                <button className="table-link" onClick={() => openInventory(row.id)}>
                  {row.number}
                </button>
              ),
            },
            { key: "started_at", label: "Início", render: (row) => fmtDate(row.started_at) },
            { key: "scope_label", label: "Abrangência" },
            {
              key: "progress",
              label: "Progresso",
              render: (row) => (
                <div className="inventory-progress-cell">
                  <strong>{fmtQty(row.counted_items)} de {fmtQty(row.total_items)}</strong>
                  <div className="inventory-progress"><span style={{ width: `${row.progress_percent || 0}%` }} /></div>
                </div>
              ),
            },
            {
              key: "divergences_count",
              label: "Divergências",
              render: (row) => (
                <StatusBadge
                  value={row.divergences_count ? "warning" : "normal"}
                  label={row.divergences_count || 0}
                />
              ),
            },
            {
              key: "status",
              label: "Situação",
              render: (row) => <StatusBadge value={row.status} label={STATUS_LABELS[row.status]} />,
            },
            { key: "user_name", label: "Responsável" },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <button className="icon-btn" onClick={() => openInventory(row.id)} title="Abrir inventário">
                  <Eye size={17} />
                </button>
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

      {form && (
        <Modal title="Iniciar novo inventário" onClose={() => setForm(null)}>
          <form className="form-grid" onSubmit={create}>
            <div className="inventory-info-box">
              <ClipboardCheck size={22} />
              <div>
                <strong>Escolha a abrangência da conferência</strong>
                <p>O sistema registrará o estoque atual como referência e aguardará a contagem física de cada produto.</p>
              </div>
            </div>
            <Field label="Categoria">
              <select
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
              >
                <option value="">Todos os produtos ativos</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Observações" hint="Opcional: motivo, setor, responsável pela contagem ou instruções.">
              <textarea
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button disabled={busy}>{busy ? "Iniciando..." : "Iniciar conferência"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {detail && localSummary && (
        <Modal title={`Inventário ${detail.number}`} onClose={() => setDetail(null)} size="xl">
          <div className="inventory-detail">
            <div className="inventory-detail-head">
              <div>
                <StatusBadge value={detail.status} label={STATUS_LABELS[detail.status]} />
                <h3>{detail.scope_label}</h3>
                <p>
                  Iniciado por <strong>{detail.user_name}</strong> em {fmtDate(detail.started_at)}
                  {detail.notes ? ` • ${detail.notes}` : ""}
                </p>
              </div>
              {detail.completed_at && <small>Concluído em {fmtDate(detail.completed_at)}</small>}
            </div>

            <div className="inventory-summary-grid">
              <div><span>Produtos</span><strong>{localSummary.total}</strong></div>
              <div><span>Conferidos</span><strong>{localSummary.counted}</strong></div>
              <div><span>Pendentes</span><strong>{localSummary.pending}</strong></div>
              <div><span>Divergências</span><strong>{localSummary.divergences}</strong></div>
              <div className="positive"><span>Sobras</span><strong>{localSummary.positive}</strong></div>
              <div className="negative"><span>Faltas</span><strong>{localSummary.negative}</strong></div>
              <div><span>Impacto estimado</span><strong>{fmtMoney(localSummary.value)}</strong></div>
            </div>

            <div className="inventory-progress-wide">
              <div>
                <strong>{localSummary.progress.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% conferido</strong>
                <span>{localSummary.pending} produto(s) ainda aguardando contagem</span>
              </div>
              <div className="inventory-progress"><span style={{ width: `${localSummary.progress}%` }} /></div>
            </div>

            {editable && (
              <div className="inventory-checklist">
                <span className={localSummary.pending === 0 ? "ok" : "pending"}>
                  <Check size={15} /> Todos os produtos foram contados
                </span>
                <span className={localSummary.missingJustification === 0 ? "ok" : "pending"}>
                  <Check size={15} /> Todas as divergências possuem justificativa
                </span>
              </div>
            )}

            <div className="inventory-items-toolbar">
              <div className="search-box">
                <Search size={17} />
                <input
                  value={itemSearch}
                  onChange={(event) => setItemSearch(event.target.value)}
                  placeholder="Pesquisar produto ou código..."
                />
              </div>
              <select value={itemFilter} onChange={(event) => setItemFilter(event.target.value)}>
                {Object.entries(ITEM_FILTERS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              {editable && (
                <Button type="button" variant="secondary" onClick={markAllAsCounted}>
                  Marcar todos sem divergência
                </Button>
              )}
            </div>

            <div className="table-wrap inventory-table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Conferido</th>
                    <th>Produto</th>
                    <th>Sistema</th>
                    <th>Contagem física</th>
                    <th>Divergência</th>
                    <th>Justificativa</th>
                    <th>Ajuste</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((item) => {
                    const draft = drafts[item.id];
                    const difference = numberValue(draft?.counted_quantity) - numberValue(item.system_quantity);
                    const needsReason = Boolean(draft?.counted && difference !== 0);
                    return (
                      <tr key={item.id} className={needsReason ? "inventory-row-divergence" : ""}>
                        <td>
                          <label className="inventory-count-check">
                            <input
                              type="checkbox"
                              checked={Boolean(draft?.counted)}
                              disabled={!editable}
                              onChange={(event) => updateDraft(item.id, { counted: event.target.checked })}
                            />
                            <span>{draft?.counted ? "Sim" : "Não"}</span>
                          </label>
                        </td>
                        <td>
                          <strong>{item.product_name}</strong>
                          <small className="block">{item.product_code} • {item.category_name}</small>
                        </td>
                        <td>{fmtQty(item.system_quantity)} {item.unit}</td>
                        <td>
                          <input
                            className="table-input"
                            type="number"
                            min="0"
                            step="1"
                            disabled={!editable}
                            value={draft?.counted_quantity ?? ""}
                            onChange={(event) => updateDraft(item.id, {
                              counted: true,
                              counted_quantity: event.target.value,
                            })}
                          />
                        </td>
                        <td>
                          {draft?.counted ? (
                            <StatusBadge
                              value={difference === 0 ? "normal" : difference > 0 ? "warning" : "danger"}
                              label={`${difference > 0 ? "+" : ""}${fmtQty(difference)}`}
                            />
                          ) : (
                            <StatusBadge value="neutral" label="Pendente" />
                          )}
                        </td>
                        <td>
                          <input
                            className={`table-input inventory-reason ${needsReason && !draft.justification.trim() ? "invalid" : ""}`}
                            disabled={!editable || !draft?.counted}
                            value={draft?.justification || ""}
                            placeholder={needsReason ? "Obrigatória para divergência" : "Opcional"}
                            onChange={(event) => updateDraft(item.id, { justification: event.target.value })}
                          />
                        </td>
                        <td>
                          {item.adjusted ? (
                            <StatusBadge value="success" label={`Mov. #${item.adjustment_movement}`} />
                          ) : (
                            fmtMoney(difference * numberValue(item.unit_cost))
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {!visibleItems.length && (
              <div className="inventory-empty-filter">Nenhum produto corresponde ao filtro selecionado.</div>
            )}

            {detail.status === "CANCELLED" && detail.cancellation_reason && (
              <div className="form-error">Motivo do cancelamento: {detail.cancellation_reason}</div>
            )}

            <div className="form-actions inventory-actions">
              {editable && (
                <>
                  <Button type="button" variant="secondary" onClick={() => saveCounts()} disabled={busy}>
                    {busy ? "Salvando..." : "Salvar contagens"}
                  </Button>
                  <Button type="button" onClick={submitInventory} disabled={busy || !canSubmit}>
                    Enviar para confirmação
                  </Button>
                </>
              )}
              {detail.status === "WAITING" && me.permissions.is_admin && (
                <>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => inventoryAction("reopen", "Inventário reaberto para nova conferência.")}
                    disabled={busy}
                  >
                    Reabrir conferência
                  </Button>
                  <Button
                    type="button"
                    onClick={() => {
                      if (window.confirm("Concluir o inventário e aplicar os ajustes de estoque?")) {
                        inventoryAction("conclude", "Inventário concluído e estoque ajustado.");
                      }
                    }}
                    disabled={busy}
                  >
                    Concluir e aplicar ajustes
                  </Button>
                </>
              )}
              {["OPEN", "WAITING"].includes(detail.status) && (
                <Button type="button" variant="danger" icon={X} onClick={cancelInventory} disabled={busy}>
                  Cancelar inventário
                </Button>
              )}
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
