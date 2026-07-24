import { React, useEffect, useMemo, useState, api, unwrap, fmtMoney, fmtQty, fmtDate, today, formatMoneyInput, toLocalDateTimeInput, getError, Logo, Button, Modal, Toast, Field, EmptyState, Pagination, DataTable, StatusBadge, AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine, BarChart3, Bell, Boxes, Check, ChevronDown, CircleDollarSign, ClipboardCheck, Eye, EyeOff, FileDown, FileText, Gauge, History, Layers3, LogOut, Menu, Package, Pencil, Plus, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal, Trash2, Truck, UserCog, Users, Warehouse, X, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";
export function DocumentPage({ type, notify, me }) {
  const isEntry = type === "entries";
  const list = useList(`${type}/`);
  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [lots, setLots] = useState([]);
  const [form, setForm] = useState(null);
  useEffect(() => { Promise.all([api.get("products/?page_size=500&active=true"), api.get("suppliers/?page_size=500&active=true"), api.get("lots/?page_size=500")]).then(([p, s, l]) => { setProducts(unwrap(p.data)); setSuppliers(unwrap(s.data)); setLots(unwrap(l.data)); }); }, []);
  const newItem = isEntry ? { product: "", quantity: "1", unit_cost: "0,00", lot_number: "", manufacturing_date: "", expiration_date: "", notes: "" } : { product: "", quantity: "1", lot: "", notes: "" };
  function start() { setForm(isEntry ? { supplier: "", entry_date: toLocalDateTimeInput(), invoice_number: "", notes: "", status: "DRAFT", items: [{ ...newItem }] } : { output_date: toLocalDateTimeInput(), reason: "COMMERCIAL", notes: "", status: "DRAFT", items: [{ ...newItem }] }); }
  function updateItem(index, key, value) { setForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, [key]: value } : item) }); }
  async function save(e) {
    e.preventDefault();
    try {
      const payload = { ...form, [isEntry ? "entry_date" : "output_date"]: new Date(form[isEntry ? "entry_date" : "output_date"]).toISOString(), items: form.items.map((item) => ({ ...item, product: Number(item.product), lot: item.lot ? Number(item.lot) : null, quantity: String(item.quantity), unit_cost: item.unit_cost != null ? String(item.unit_cost) : undefined, manufacturing_date: item.manufacturing_date || null, expiration_date: item.expiration_date || null })) };
      if (form.id) await api.put(`${type}/${form.id}/`, payload); else await api.post(`${type}/`, payload);
      notify(`${isEntry ? "Entrada" : "Saída"} salva como rascunho.`); setForm(null); list.reload();
    } catch (err) { notify(getError(err), "error"); }
  }
  async function action(row, name) {
    const label = name === "confirm" ? "confirmar" : "cancelar e estornar";
    if (!confirm(`Deseja ${label} ${row.number}?`)) return;
    try { await api.post(`${type}/${row.id}/${name}/`); notify(`Operação realizada em ${row.number}.`); list.reload(); } catch (err) { notify(getError(err), "error"); }
  }
  return <>
    <PageHeader title={isEntry ? "Entradas de estoque" : "Saídas de estoque"} description={isEntry ? "Recebimentos com lotes, validade, custos e nota fiscal." : "Retiradas internas com controle FEFO e bloqueio de estoque negativo."} actions={<Button icon={Plus} onClick={start}>{isEntry ? "Nova entrada" : "Nova saída"}</Button>} />
    <div className="filters-bar"><SearchBar value={list.params.search || ""} onChange={(search) => list.setParams({ ...list.params, search, page: 1 })} /><select value={list.params.status || ""} onChange={(e) => list.setParams({ ...list.params, status: e.target.value, page: 1 })}><option value="">Todas as situações</option><option value="DRAFT">Rascunho</option><option value="CONFIRMED">Confirmada</option><option value="CANCELLED">Cancelada</option></select></div>
    <section className="panel"><DataTable loading={list.loading} rows={list.rows} columns={[
      { key: "number", label: "Número", render: (r) => <strong>{r.number}</strong> },
      { key: "date", label: "Data", render: (r) => fmtDate(r[isEntry ? "entry_date" : "output_date"]) },
      ...(isEntry ? [{ key: "supplier_name", label: "Fornecedor" }, { key: "invoice_number", label: "Nota fiscal" }, { key: "total_value", label: "Valor total", render: (r) => fmtMoney(r.total_value) }] : [{ key: "reason_display", label: "Motivo" }]),
      { key: "items", label: "Itens", render: (r) => r.items?.length || 0 },
      { key: "status", label: "Situação", render: (r) => <StatusBadge value={r.status} label={r.status === "DRAFT" ? "Rascunho" : r.status === "CONFIRMED" ? "Confirmada" : "Cancelada"} /> },
      { key: "user_name", label: "Responsável" },
      { key: "actions", label: "Ações", render: (r) => <div className="row-actions">{r.status === "DRAFT" && <><button onClick={() => setForm({ ...r, [isEntry ? "entry_date" : "output_date"]: toLocalDateTimeInput(r[isEntry ? "entry_date" : "output_date"]), items: r.items.map((item) => ({ ...item, quantity: String(item.quantity), ...(isEntry ? { unit_cost: formatMoneyInput(item.unit_cost) } : {}) })) })}><Pencil size={16} /></button><button className="success" onClick={() => action(r, "confirm")}><Check size={16} /></button></>}{r.status === "CONFIRMED" && me.permissions.is_admin && <button className="danger" onClick={() => action(r, "cancel")}><X size={16} /></button>}</div> },
    ]} /><Pagination page={list.params.page} count={list.count} onChange={(page) => list.setParams({ ...list.params, page })} /></section>
    {form && <Modal title={`${form.id ? "Editar" : "Nova"} ${isEntry ? "entrada" : "saída"}`} onClose={() => setForm(null)} size="xl"><form onSubmit={save} className="document-form">
      <div className="form-grid cols-3">
        {isEntry && <Field label="Fornecedor" required><select value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} required><option value="">Selecione</option>{suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>}
        <Field label={isEntry ? "Data da entrada" : "Data da saída"} required><input type="datetime-local" value={form[isEntry ? "entry_date" : "output_date"]} onChange={(e) => setForm({ ...form, [isEntry ? "entry_date" : "output_date"]: e.target.value })} required /></Field>
        {isEntry ? <Field label="Número da nota fiscal"><input value={form.invoice_number || ""} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></Field> : <Field label="Motivo" required><select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}><option value="COMMERCIAL">Retirada para comercialização</option><option value="TRANSFER">Transferência</option><option value="LOSS">Perda</option><option value="DAMAGE">Avaria</option><option value="EXPIRED">Produto vencido</option><option value="INTERNAL">Consumo interno</option><option value="DONATION">Doação</option><option value="ADJUSTMENT">Ajuste</option><option value="OTHER">Outros</option></select></Field>}
        <Field label="Observações"><textarea value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
      </div>
      <div className="items-editor"><div className="items-header"><h3>Produtos</h3><Button type="button" variant="secondary" icon={Plus} onClick={() => setForm({ ...form, items: [...form.items, { ...newItem }] })}>Adicionar item</Button></div>
        {form.items.map((item, index) => <div className="item-row" key={index}>
          <Field label="Produto" required><select value={item.product} onChange={(e) => updateItem(index, "product", e.target.value)} required><option value="">Selecione</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name} — estoque {fmtQty(p.stock)}</option>)}</select></Field>
          <Field label="Quantidade" required><input type="number" min="1" step="1" value={item.quantity} onChange={(e) => updateItem(index, "quantity", e.target.value)} required /></Field>
          {isEntry ? <><Field label="Custo unitário" required hint="Aceita vírgula ou ponto."><input type="text" inputMode="decimal" value={item.unit_cost} onChange={(e) => updateItem(index, "unit_cost", e.target.value)} onBlur={() => updateItem(index, "unit_cost", formatMoneyInput(item.unit_cost))} required /></Field><Field label="Lote"><input value={item.lot_number || ""} onChange={(e) => updateItem(index, "lot_number", e.target.value)} /></Field><Field label="Fabricação"><input type="date" value={item.manufacturing_date || ""} onChange={(e) => updateItem(index, "manufacturing_date", e.target.value)} /></Field><Field label="Validade"><input type="date" value={item.expiration_date || ""} onChange={(e) => updateItem(index, "expiration_date", e.target.value)} /></Field></> : <Field label="Lote (opcional)"><select value={item.lot || ""} onChange={(e) => updateItem(index, "lot", e.target.value)}><option value="">Automático — FEFO</option>{lots.filter((l) => String(l.product) === String(item.product) && Number(l.quantity) > 0).map((l) => <option key={l.id} value={l.id}>{l.number} — {fmtQty(l.quantity)} — {l.expiration_date || "sem validade"}</option>)}</select></Field>}
          <button type="button" className="icon-btn danger" disabled={form.items.length === 1} onClick={() => setForm({ ...form, items: form.items.filter((_, i) => i !== index) })}><Trash2 size={16} /></button>
        </div>)}
      </div>
      <div className="form-actions"><Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button><Button>Salvar rascunho</Button></div>
    </form></Modal>}
  </>;
}
