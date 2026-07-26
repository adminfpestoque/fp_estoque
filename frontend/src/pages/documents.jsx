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
  formatMoneyInput,
  parseLocalizedNumber,
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
  CircleDollarSign,
  Eye,
  Pencil,
  Plus,
  Trash2,
  X,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { SearchBar, useList } from "./listing.jsx";

const PAYMENT_METHODS = [
  ["CASH", "Dinheiro"],
  ["PIX", "Pix"],
  ["DEBIT", "Cartão de débito"],
  ["CREDIT", "Cartão de crédito"],
  ["TRANSFER", "Transferência"],
  ["ON_ACCOUNT", "A prazo/fiado"],
  ["OTHER", "Outro"],
];

function documentStatus(row) {
  if (row.is_deleted) return ["DELETED", "Excluída"];
  if (row.status === "DRAFT") return [row.status, "Rascunho"];
  if (row.status === "CONFIRMED") return [row.status, "Confirmada"];
  return [row.status, "Cancelada"];
}

function movementUnitOptions(product) {
  const unitOption = {
    id: "",
    name: "Unidade",
    factor: 1,
    costPrice: parseLocalizedNumber(product?.cost_price),
    salePrice: parseLocalizedNumber(product?.sale_price),
    isDefault: !(product?.packaging_options || []).some((option) => option.active && option.is_default),
  };
  if (!product) return [unitOption];
  return [
    unitOption,
    ...(product.packaging_options || [])
      .filter((option) => option.active && Number(option.units_per_package) > 1)
      .map((option) => ({
        id: String(option.id),
        name: option.packaging_type_name || option.display_name || option.name || "Embalagem",
        factor: Number(option.units_per_package),
        costPrice: parseLocalizedNumber(option.cost_price),
        salePrice: parseLocalizedNumber(option.sale_price),
        isDefault: Boolean(option.is_default),
      })),
  ];
}

function defaultMovementOption(product) {
  const options = movementUnitOptions(product);
  return options.find((option) => option.isDefault) || options[0];
}

function quantityFieldLabel(option) {
  if (!option || option.factor === 1) return "Quantidade de unidades";
  return `Quantidade de ${option.name}`;
}

function costFieldLabel(option) {
  if (!option || option.factor === 1) return "Preço de custo por unidade";
  return `Preço de custo por ${option.name}`;
}


function OutputDetails({ row, onClose }) {
  return (
    <Modal title={`Saída ${row.number}`} onClose={onClose} size="lg">
      <div className="checkout-detail-grid">
        <div><span>Situação</span><strong>{row.display_status}</strong></div>
        <div><span>Data</span><strong>{fmtDate(row.output_date)}</strong></div>
        <div><span>Cliente</span><strong>{row.customer_name || "Cliente não informado"}</strong></div>
        <div><span>Motivo</span><strong>{row.reason_display}</strong></div>
        <div><span>Pagamento</span><strong>{row.payment_method_display || "Não se aplica"}</strong></div>
        <div><span>Total</span><strong>{fmtMoney(row.total_value)}</strong></div>
        {row.payment_method === "CASH" && (
          <>
            <div><span>Valor recebido</span><strong>{fmtMoney(row.amount_received)}</strong></div>
            <div><span>Troco</span><strong>{fmtMoney(row.change_amount)}</strong></div>
          </>
        )}
      </div>

      <div className="checkout-detail-items">
        <h3>Itens retirados</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Produto</th><th>Forma</th><th>Quantidade</th><th>Baixa no estoque</th><th>Preço</th><th>Subtotal</th></tr></thead>
            <tbody>
              {(row.items || []).map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.product_name}</strong><small className="block">{item.product_code}</small></td>
                  <td>{item.sale_unit_description || item.sale_unit_name || "Unidade"}</td>
                  <td>{fmtQty(item.sale_quantity || item.quantity)}</td>
                  <td>{fmtQty(item.quantity)} UN</td>
                  <td>{fmtMoney(item.sale_price ?? item.unit_sale_price)} por {item.sale_unit_name || "Unidade"}</td>
                  <td>{fmtMoney(item.subtotal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {row.deletion_reason && <div className="document-edit-warning neutral">Motivo da exclusão: {row.deletion_reason}</div>}
      <div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Fechar</Button></div>
    </Modal>
  );
}

export function DocumentPage({ type, notify, me }) {
  const isEntry = type === "entries";
  const list = useList(`${type}/`);
  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [lots, setLots] = useState([]);
  const [form, setForm] = useState(null);
  const [detailRow, setDetailRow] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("products/?page_size=500&deleted=false"),
      api.get("suppliers/?page_size=500&active=true"),
      api.get("lots/?page_size=500&balance=positive"),
    ])
      .then(([productResponse, supplierResponse, lotResponse]) => {
        setProducts(unwrap(productResponse.data));
        setSuppliers(unwrap(supplierResponse.data));
        setLots(unwrap(lotResponse.data));
      })
      .catch((error) => notify(getError(error), "error"));
  }, []);

  const entryItem = {
    product: "",
    packaging: "",
    entry_quantity: "1",
    purchase_price: "0,00",
    lot_number: "",
    manufacturing_date: "",
    expiration_date: "",
  };
  const outputItem = {
    product: "",
    packaging: "",
    sale_quantity: "1",
    lot: "",
    notes: "",
  };

  function start() {
    setForm(
      isEntry
        ? {
            supplier: "",
            entry_date: toLocalDateTimeInput(),
            invoice_number: "",
            notes: "",
            items: [{ ...entryItem }],
          }
        : {
            output_date: toLocalDateTimeInput(),
            reason: "COMMERCIAL",
            customer_name: "",
            payment_method: "CASH",
            amount_received: "0,00",
            payment_reference: "",
            notes: "",
            items: [{ ...outputItem }],
          },
    );
  }

  function edit(row) {
    if (row.is_deleted || row.status === "CANCELLED") return;
    setForm({
      ...row,
      [isEntry ? "entry_date" : "output_date"]: toLocalDateTimeInput(
        row[isEntry ? "entry_date" : "output_date"],
      ),
      amount_received: formatMoneyInput(row.amount_received || 0),
      payment_method:
        !isEntry && row.reason === "COMMERCIAL" && row.payment_method === "NONE"
          ? "OTHER"
          : row.payment_method,
      items: row.items.map((item) => ({
        ...item,
        product: item.product || "",
        ...(isEntry
          ? {
              packaging: item.packaging || "",
              entry_quantity: String(item.entry_quantity || item.quantity || 1),
              purchase_price: formatMoneyInput(item.purchase_price ?? item.unit_cost ?? 0),
            }
          : {
              packaging: item.packaging || "",
              sale_quantity: String(item.sale_quantity || item.quantity || 1),
            }),
      })),
    });
  }

  function updateItem(index, key, value) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    }));
  }

  function changeEntryProduct(index, productId) {
    const product = products.find((row) => String(row.id) === String(productId));
    const selected = defaultMovementOption(product);
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              product: productId,
              packaging: selected.id,
              entry_quantity: "1",
              purchase_price: formatMoneyInput(selected.costPrice),
              lot_number: "",
            }
          : item,
      ),
    }));
  }

  function changeEntryUnit(index, packagingId) {
    const item = form.items[index];
    const product = products.find((row) => String(row.id) === String(item.product));
    const selected = movementUnitOptions(product).find(
      (option) => String(option.id) === String(packagingId),
    ) || movementUnitOptions(product)[0];
    setForm((current) => ({
      ...current,
      items: current.items.map((row, itemIndex) =>
        itemIndex === index
          ? {
              ...row,
              packaging: selected.id,
              purchase_price: formatMoneyInput(selected.costPrice),
            }
          : row,
      ),
    }));
  }

  function changeOutputProduct(index, productId) {
    const product = products.find((row) => String(row.id) === String(productId));
    const selected = defaultMovementOption(product);
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, product: productId, packaging: selected.id, sale_quantity: "1", lot: "" }
          : item,
      ),
    }));
  }

  function changeSaleUnit(index, packagingId) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, packaging: packagingId || "", sale_quantity: item.sale_quantity || "1" }
          : item,
      ),
    }));
  }

  const entryCalculation = useMemo(() => {
    if (!form || !isEntry) return { lines: [], total: 0, units: 0, invalidSelection: false };
    let invalidSelection = false;
    const lines = form.items.map((item) => {
      const product = products.find((row) => String(row.id) === String(item.product));
      const options = movementUnitOptions(product);
      const selected = options.find((option) => String(option.id) === String(item.packaging));
      if (item.packaging && !selected) invalidSelection = true;
      const effectiveOption = selected || options[0];
      const entryQuantity = Math.max(0, Math.trunc(parseLocalizedNumber(item.entry_quantity)));
      const stockQuantity = entryQuantity * effectiveOption.factor;
      const purchasePrice = parseLocalizedNumber(item.purchase_price);
      const subtotal = entryQuantity * purchasePrice;
      const unitCost = effectiveOption.factor ? purchasePrice / effectiveOption.factor : purchasePrice;
      return { product, selected: effectiveOption, entryQuantity, stockQuantity, purchasePrice, unitCost, subtotal };
    });
    return {
      lines,
      total: lines.reduce((sum, line) => sum + line.subtotal, 0),
      units: lines.reduce((sum, line) => sum + line.stockQuantity, 0),
      invalidSelection,
    };
  }, [form, isEntry, products]);


  const outputCalculation = useMemo(() => {
    if (!form || isEntry) {
      return {
        lines: [], total: 0, received: 0, change: 0, missing: 0,
        invalidStock: false, invalidSelection: false,
      };
    }
    const productTotals = new Map();
    let invalidSelection = false;
    const lines = form.items.map((item) => {
      const product = products.find((row) => String(row.id) === String(item.product));
      const options = movementUnitOptions(product);
      const selected = options.find((row) => String(row.id) === String(item.packaging));
      if (item.packaging && !selected) invalidSelection = true;
      const effectiveOption = selected || options[0];
      const saleQuantity = Math.max(0, Math.trunc(parseLocalizedNumber(item.sale_quantity)));
      const stockQuantity = saleQuantity * effectiveOption.factor;
      const formPrice = effectiveOption.salePrice;
      const unitPrice = effectiveOption.factor ? formPrice / effectiveOption.factor : formPrice;
      const subtotal = saleQuantity * formPrice;
      const currentStock = parseLocalizedNumber(product?.stock);
      const alreadySelected = product ? (productTotals.get(product.id) || 0) : 0;
      const cumulativeQuantity = alreadySelected + stockQuantity;
      if (product) productTotals.set(product.id, cumulativeQuantity);
      return {
        product,
        selected: effectiveOption,
        saleQuantity,
        stockQuantity,
        formPrice,
        unitPrice,
        subtotal,
        currentStock,
        remainingStock: currentStock - cumulativeQuantity,
      };
    });
    const total = lines.reduce((sum, line) => sum + line.subtotal, 0);
    const received = parseLocalizedNumber(form.amount_received);
    const change = form.payment_method === "CASH" ? Math.max(received - total, 0) : 0;
    const missing = form.payment_method === "CASH" ? Math.max(total - received, 0) : 0;
    const invalidStock = [...productTotals.entries()].some(([productId, quantity]) => {
      const product = products.find((row) => row.id === productId);
      return quantity > parseLocalizedNumber(product?.stock);
    });
    return { lines, total, received, change, missing, invalidStock, invalidSelection };
  }, [form, isEntry, products]);

  function buildPayload() {
    const dateField = isEntry ? "entry_date" : "output_date";
    if (isEntry) {
      return {
        supplier: Number(form.supplier),
        entry_date: new Date(form[dateField]).toISOString(),
        invoice_number: "",
        notes: "",
        items: form.items.map((item) => ({
          product: Number(item.product),
          packaging: item.packaging ? Number(item.packaging) : null,
          entry_quantity: String(item.entry_quantity),
          purchase_price: String(item.purchase_price),
          lot_number: item.lot_number || "",
          manufacturing_date: item.manufacturing_date || null,
          expiration_date: item.expiration_date || null,
          notes: "",
        })),
      };
    }
    return {
      output_date: new Date(form.output_date).toISOString(),
      reason: form.reason,
      customer_name: form.customer_name?.trim() || "",
      payment_method: form.reason === "COMMERCIAL" ? form.payment_method : "NONE",
      amount_received:
        form.reason === "COMMERCIAL" && form.payment_method === "CASH"
          ? String(form.amount_received)
          : "0,00",
      payment_reference: form.reason === "COMMERCIAL" ? form.payment_reference?.trim() || "" : "",
      notes: form.notes || "",
      items: form.items.map((item) => ({
        product: Number(item.product),
        packaging: item.packaging ? Number(item.packaging) : null,
        sale_quantity: String(item.sale_quantity),
        lot: item.lot ? Number(item.lot) : null,
        notes: item.notes || "",
      })),
    };
  }

  async function save(event, finalize = false) {
    event?.preventDefault?.();
    if (isEntry && entryCalculation.invalidSelection) {
      notify("Selecione novamente a forma de entrada de um dos produtos.", "error");
      return;
    }
    if (!isEntry) {
      if (outputCalculation.invalidSelection) {
        notify("Selecione novamente a forma de retirada de um dos produtos.", "error");
        return;
      }
      if (outputCalculation.invalidStock) {
        notify("A quantidade informada supera o estoque disponível de um dos produtos.", "error");
        return;
      }
      if (finalize && form.reason === "COMMERCIAL" && form.payment_method === "CASH" && outputCalculation.missing > 0) {
        notify(`O valor recebido é insuficiente. Faltam ${fmtMoney(outputCalculation.missing)}.`, "error");
        return;
      }
    }

    setBusy(true);
    try {
      const payload = buildPayload();
      let response;
      if (form.id) response = await api.put(`${type}/${form.id}/`, payload);
      else response = await api.post(`${type}/`, payload);

      let result = response.data;
      if (!isEntry && finalize && result.status === "DRAFT") {
        result = (await api.post(`${type}/${result.id}/confirm/`)).data;
      }

      if (form.id) {
        notify(
          form.status === "CONFIRMED"
            ? `${isEntry ? "Entrada" : "Saída"} atualizada e estoque recalculado.`
            : `${isEntry ? "Entrada" : "Saída"} atualizada com sucesso.`,
        );
      } else if (!isEntry && finalize) {
        notify("Venda finalizada e estoque atualizado.");
      } else {
        notify(`${isEntry ? "Entrada" : "Saída"} salva como rascunho.`);
      }
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function executeAction() {
    if (!pendingAction) return;
    const { row, action } = pendingAction;
    setBusy(true);
    try {
      if (action === "delete") {
        await api.delete(`${type}/${row.id}/`, { data: { reason: "Exclusão solicitada pelo usuário" } });
        notify(`${isEntry ? "Entrada" : "Saída"} excluída do uso operacional e mantida no histórico.`);
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
        detail: "O registro continuará no histórico em cinza como Excluído. Se estiver confirmado, o estoque será estornado antes da exclusão lógica.",
        confirmLabel: `Excluir ${isEntry ? "entrada" : "saída"}`,
        confirmVariant: "danger",
      };
    }
    if (action === "confirm") {
      return {
        title: `Confirmar ${isEntry ? "entrada" : "saída"}`,
        message: `Deseja confirmar “${row.number}”?`,
        detail: isEntry
          ? "A confirmação atualizará o estoque com os itens informados."
          : "A confirmação finalizará a retirada, registrará o pagamento e atualizará o estoque.",
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
        title={isEntry ? "Entradas de estoque" : "Saídas e caixa"}
        description={
          isEntry
            ? "Registre os produtos recebidos e o sistema atualizará o estoque em unidades individuais."
            : "Registre vendas e outras retiradas com cálculo automático do estoque e do pagamento."
        }
        actions={<Button icon={Plus} onClick={start}>{isEntry ? "Nova entrada" : "Nova saída"}</Button>}
      />

      <div className="filters-bar">
        <SearchBar value={list.params.search || ""} onChange={(search) => list.setParams({ ...list.params, search, page: 1 })} />
        <select value={statusFilter} onChange={(event) => changeStatusFilter(event.target.value)}>
          <option value="">Todas as situações</option>
          <option value="DRAFT">Rascunho</option>
          <option value="CONFIRMED">Confirmada</option>
          <option value="CANCELLED">Cancelada</option>
          <option value="DELETED">Excluída</option>
        </select>
        {!isEntry && (
          <select value={list.params.payment_method || ""} onChange={(event) => list.setParams({ ...list.params, payment_method: event.target.value, page: 1 })}>
            <option value="">Todas as formas de pagamento</option>
            {PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        )}
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
              render: (row) => <span><strong>{row.number}</strong>{row.is_deleted && <small className="block">Mantida somente para histórico</small>}</span>,
            },
            { key: "date", label: "Data", render: (row) => fmtDate(row[isEntry ? "entry_date" : "output_date"]) },
            ...(isEntry
              ? [
                  { key: "supplier_name", label: "Fornecedor" },
                  { key: "total_value", label: "Valor total da compra", render: (row) => fmtMoney(row.total_value) },
                ]
              : [
                  { key: "customer_name", label: "Cliente", render: (row) => row.customer_name || "Balcão" },
                  { key: "payment_method_display", label: "Pagamento", render: (row) => row.reason === "COMMERCIAL" ? row.payment_method_display : "Não se aplica" },
                  { key: "total_value", label: "Total", render: (row) => fmtMoney(row.total_value) },
                ]),
            { key: "items", label: "Itens", render: (row) => row.items?.length || 0 },
            { key: "status", label: "Situação", render: (row) => { const [value, label] = documentStatus(row); return <StatusBadge value={value} label={label} />; } },
            { key: "user_name", label: "Responsável" },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <div className="row-actions">
                  {!isEntry && <button onClick={() => setDetailRow(row)} title="Visualizar saída"><Eye size={16} /></button>}
                  {!row.is_deleted && row.status !== "CANCELLED" && (
                    <button onClick={() => edit(row)} title={row.status === "CONFIRMED" ? "Editar e recalcular estoque" : "Editar"}><Pencil size={16} /></button>
                  )}
                  {!row.is_deleted && row.status === "DRAFT" && (
                    <button className="success" onClick={() => setPendingAction({ row, action: "confirm" })} title="Confirmar"><Check size={16} /></button>
                  )}
                  {!row.is_deleted && row.status === "CONFIRMED" && me.permissions.is_admin && (
                    <button className="warning" onClick={() => setPendingAction({ row, action: "cancel" })} title="Cancelar e estornar"><X size={16} /></button>
                  )}
                  {!row.is_deleted && me.permissions.is_admin && (
                    <button className="danger" onClick={() => setPendingAction({ row, action: "delete" })} title={`Excluir ${isEntry ? "entrada" : "saída"}`}><Trash2 size={16} /></button>
                  )}
                  {row.is_deleted && isEntry && <span className="muted-text">Histórico</span>}
                </div>
              ),
            },
          ]}
        />
        <Pagination page={list.params.page} count={list.count} onChange={(page) => list.setParams({ ...list.params, page })} />
      </section>

      {form && isEntry && (
        <Modal title={`${form.id ? "Editar" : "Nova"} entrada`} onClose={() => !busy && setForm(null)} size="xl">
          <form onSubmit={save} className="document-form entry-form">
            {form.id && form.status === "CONFIRMED" && <div className="document-edit-warning">Ao salvar, o sistema estornará a movimentação anterior e aplicará novamente as quantidades e os custos corrigidos.</div>}
            <div className="form-grid cols-2">
              <Field label="Fornecedor da compra" required><select value={form.supplier} onChange={(event) => setForm({ ...form, supplier: event.target.value })} required><option value="">Selecione o fornecedor</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></Field>
              <Field label="Data e hora da entrada" required><input type="datetime-local" value={form.entry_date} onChange={(event) => setForm({ ...form, entry_date: event.target.value })} required /></Field>
            </div>

            <div className="checkout-products-heading"><div><h3>Itens da entrada</h3><p>Selecione o produto, a forma recebida e a quantidade.</p></div><Button type="button" variant="secondary" icon={Plus} onClick={() => setForm({ ...form, items: [...form.items, { ...entryItem }] })}>Adicionar produto</Button></div>

            <div className="checkout-items entry-items">
              {form.items.map((item, index) => {
                const line = entryCalculation.lines[index];
                const product = line?.product;
                const options = movementUnitOptions(product);
                return (
                  <div className="checkout-item-card entry-item-card" key={item.id || index}>
                    <div className="checkout-item-number">{index + 1}</div>
                    <div className="entry-item-fields">
                      <Field label="Produto" required><select value={item.product || ""} onChange={(event) => changeEntryProduct(index, event.target.value)} required><option value="">Selecione o produto</option>{products.filter((row) => row.active || String(row.id) === String(item.product)).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
                      <Field label="Recebido em" required hint={!product ? "Selecione o produto primeiro." : "A forma padrão do produto já vem selecionada, mas pode ser alterada para Unidade ou outra embalagem."}><select value={item.packaging || ""} onChange={(event) => changeEntryUnit(index, event.target.value)} disabled={!product} required>{options.map((option) => <option key={option.id || "unit"} value={option.id}>{option.name} — contém {option.factor} {option.factor === 1 ? "unidade" : "unidades"}</option>)}</select></Field>
                      <Field label={quantityFieldLabel(line?.selected)} required hint="Digite a quantidade da forma selecionada."><input type="number" min="1" step="1" value={item.entry_quantity} onChange={(event) => updateItem(index, "entry_quantity", event.target.value)} required /></Field>
                      <Field label={costFieldLabel(line?.selected)} required hint="Valor pago por uma unidade da forma selecionada."><input type="text" inputMode="decimal" value={item.purchase_price} onChange={(event) => updateItem(index, "purchase_price", event.target.value)} onBlur={() => updateItem(index, "purchase_price", formatMoneyInput(item.purchase_price))} required /></Field>
                      <Field label="Número ou identificação do lote"><input value={item.lot_number || ""} onChange={(event) => updateItem(index, "lot_number", event.target.value)} placeholder="Opcional" /></Field>
                      <Field label="Data de fabricação"><input type="date" value={item.manufacturing_date || ""} onChange={(event) => updateItem(index, "manufacturing_date", event.target.value)} /></Field>
                      <Field label="Data de validade"><input type="date" value={item.expiration_date || ""} onChange={(event) => updateItem(index, "expiration_date", event.target.value)} /></Field>
                    </div>
                    <div className="checkout-item-summary entry-item-summary">
                      <span>Entrada no estoque</span>
                      <strong>{fmtQty(line?.entryQuantity || 0)} {line?.selected?.name || "Unidade"}</strong>
                      <div className="checkout-conversion-equation"><span>{fmtQty(line?.entryQuantity || 0)} × {fmtQty(line?.selected?.factor || 1)}</span><b>=</b><strong>{fmtQty(line?.stockQuantity || 0)} unidades</strong></div>
                      
                      <span>Valor total deste item</span>
                      <strong>{fmtMoney(line?.subtotal || 0)}</strong>
                    </div>
                    <button type="button" className="icon-btn danger checkout-remove" disabled={form.items.length === 1} onClick={() => setForm({ ...form, items: form.items.filter((_, itemIndex) => itemIndex !== index) })} aria-label="Remover produto"><Trash2 size={16} /></button>
                  </div>
                );
              })}
            </div>

            <div className="entry-total-summary"><span>Unidades adicionadas: <strong>{fmtQty(entryCalculation.units)} UN</strong></span><span>Total da entrada: <strong>{fmtMoney(entryCalculation.total)}</strong></span></div>
            <div className="form-actions"><Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancelar</Button><Button disabled={busy || entryCalculation.invalidSelection}>{busy ? "Salvando..." : form.id ? "Salvar alterações" : "Salvar rascunho"}</Button></div>
          </form>
        </Modal>
      )}

      {form && !isEntry && (
        <Modal title={`${form.id ? "Editar" : "Nova"} saída`} onClose={() => !busy && setForm(null)} size="xl">
          <form onSubmit={save} className="checkout-form">
            {form.id && form.status === "CONFIRMED" && <div className="document-edit-warning">Esta venda já movimentou o estoque. Ao salvar, o sistema estornará a versão anterior e aplicará novamente os valores corrigidos.</div>}
            <div className="checkout-layout">
              <div className="checkout-main">
                <div className="form-grid cols-3">
                  <Field label="Data da saída" required><input type="datetime-local" value={form.output_date} onChange={(event) => setForm({ ...form, output_date: event.target.value })} required /></Field>
                  <Field label="Motivo" required><select value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value, payment_method: event.target.value === "COMMERCIAL" ? (form.payment_method === "NONE" ? "CASH" : form.payment_method) : "NONE" })}><option value="COMMERCIAL">Retirada para comercialização</option><option value="TRANSFER">Transferência</option><option value="LOSS">Perda</option><option value="DAMAGE">Avaria</option><option value="EXPIRED">Produto vencido</option><option value="INTERNAL">Consumo interno</option><option value="DONATION">Doação</option><option value="ADJUSTMENT">Ajuste</option><option value="OTHER">Outros</option></select></Field>
                  <Field label="Cliente"><input value={form.customer_name || ""} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} placeholder="Nome ou identificação do cliente" /></Field>
                </div>

                <div className="checkout-products-heading"><div><h3>Itens da saída</h3><p>Selecione o produto, a forma de retirada e a quantidade.</p></div><Button type="button" variant="secondary" icon={Plus} onClick={() => setForm({ ...form, items: [...form.items, { ...outputItem }] })}>Adicionar produto</Button></div>

                <div className="checkout-items">
                  {form.items.map((item, index) => {
                    const line = outputCalculation.lines[index];
                    const product = line?.product;
                    const options = movementUnitOptions(product);
                    const lineInsufficient = product && line.stockQuantity > parseLocalizedNumber(product.stock);
                    return (
                      <div className={`checkout-item-card ${lineInsufficient ? "invalid" : ""}`} key={item.id || index}>
                        <div className="checkout-item-number">{index + 1}</div>
                        <div className="checkout-item-fields">
                          <Field label="Produto" required><select value={item.product || ""} onChange={(event) => changeOutputProduct(index, event.target.value)} required><option value="">Selecione o produto</option>{products.filter((row) => row.active || String(row.id) === String(item.product)).map((row) => <option key={row.id} value={row.id}>{row.name} — {fmtQty(row.stock)} unidades disponíveis</option>)}</select></Field>
                          <Field
                            label="Retirar em"
                            hint={
                              !product
                                ? "Selecione o produto primeiro."
                                : options.length === 1
                                  ? "Somente Unidade está configurada. Cadastre Caixa, Fardo ou Grade em Produtos > Editar."
                                  : "A lista mostra somente as formas cadastradas para este produto."
                            }
                          >
                            <select value={item.packaging || ""} onChange={(event) => changeSaleUnit(index, event.target.value)} disabled={!product}>
                              {options.map((option) => (
                                <option key={option.id || "unit"} value={option.id}>
                                  {option.name} — {option.factor === 1 ? "baixa 1 unidade" : `baixa ${option.factor} unidades`}
                                </option>
                              ))}
                            </select>
                          </Field>
                          <Field label={`Quantidade de ${line?.selected?.name || "Unidade"}`} required hint="Informe quantas unidades, caixas, fardos ou grades serão retirados."><input type="number" min="1" step="1" value={item.sale_quantity} onChange={(event) => updateItem(index, "sale_quantity", event.target.value)} required /></Field>
                          <Field label="Lote (opcional)" hint="Opcional: o sistema usa primeiro o lote que vence antes."><select value={item.lot || ""} onChange={(event) => updateItem(index, "lot", event.target.value)} disabled={!product}><option value="">Automático por validade</option>{lots.filter((lot) => String(lot.product) === String(item.product) && (Number(lot.quantity) > 0 || String(lot.id) === String(item.lot))).map((lot) => <option key={lot.id} value={lot.id}>{lot.number} — {fmtQty(lot.quantity)} unidades — {lot.expiration_date || "sem validade"}</option>)}</select></Field>
                        </div>
                        <div className="checkout-item-summary">
                          <span>Baixa no estoque</span>
                          <strong>{fmtQty(line?.saleQuantity || 0)} {line?.selected?.name || "Unidade"}</strong>
                          <div className="checkout-conversion-equation">
                            <span>{fmtQty(line?.saleQuantity || 0)} × {fmtQty(line?.selected?.factor || 1)}</span>
                            <b>=</b>
                            <strong>{fmtQty(line?.stockQuantity || 0)} unidades</strong>
                          </div>
                          <small>Estoque: {fmtQty(line?.currentStock || 0)} → {fmtQty(line?.remainingStock || 0)} unidades</small>
                          <span>{fmtMoney(line?.formPrice || 0)} por {line?.selected?.name || "Unidade"}</span>
                          
                          <strong>{fmtMoney(line?.subtotal || 0)}</strong>
                          {lineInsufficient && <small className="checkout-error">Estoque insuficiente</small>}
                        </div>
                        <button type="button" className="icon-btn danger checkout-remove" disabled={form.items.length === 1} onClick={() => setForm({ ...form, items: form.items.filter((_, itemIndex) => itemIndex !== index) })} aria-label="Remover produto"><Trash2 size={16} /></button>
                      </div>
                    );
                  })}
                </div>
              </div>

              <aside className="checkout-summary">
                <div className="checkout-summary-title"><CircleDollarSign size={22} /><div><strong>Resumo do caixa</strong><small>{form.reason === "COMMERCIAL" ? "Venda e pagamento" : "Retirada sem cobrança"}</small></div></div>
                <div className="checkout-total-row"><span>{form.reason === "COMMERCIAL" ? "Total da venda" : "Valor da saída"}</span><strong>{fmtMoney(outputCalculation.total)}</strong></div>

                {form.reason === "COMMERCIAL" ? (
                  <>
                    <Field label="Forma de pagamento" required><select value={form.payment_method} onChange={(event) => setForm({ ...form, payment_method: event.target.value, amount_received: event.target.value === "CASH" ? form.amount_received : formatMoneyInput(outputCalculation.total) })} required>{PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
                    {form.payment_method === "CASH" && (
                      <Field label="Valor recebido" required hint="Digite o valor entregue pelo cliente."><input type="text" inputMode="decimal" value={form.amount_received} onChange={(event) => setForm({ ...form, amount_received: event.target.value })} onBlur={() => setForm((current) => ({ ...current, amount_received: formatMoneyInput(current.amount_received) }))} required /></Field>
                    )}
                    {!["CASH", "PIX", "DEBIT", "CREDIT"].includes(form.payment_method) && (
                      <Field label="Referência do pagamento"><input value={form.payment_reference || ""} onChange={(event) => setForm({ ...form, payment_reference: event.target.value })} placeholder="Comprovante, observação ou prazo" /></Field>
                    )}
                    {form.payment_method === "CASH" && (
                      <div className={`checkout-change ${outputCalculation.missing > 0 ? "missing" : ""}`}><span>{outputCalculation.missing > 0 ? "Valor que falta" : "Troco"}</span><strong>{fmtMoney(outputCalculation.missing > 0 ? outputCalculation.missing : outputCalculation.change)}</strong></div>
                    )}
                  </>
                ) : <div className="checkout-no-payment">Esta retirada não exige forma de pagamento. O estoque será atualizado normalmente.</div>}

                <div className="checkout-stock-note"><strong>{fmtQty(outputCalculation.lines.reduce((sum, line) => sum + line.stockQuantity, 0))} UN</strong><span>Unidades retiradas do estoque</span></div>
                {outputCalculation.invalidStock && <div className="checkout-warning">Revise as quantidades: um produto não possui estoque suficiente.</div>}
              </aside>
            </div>

            <div className="form-actions checkout-actions">
              <Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
              {(!form.id || form.status === "DRAFT") && <Button type="submit" variant="secondary" disabled={busy}>{busy ? "Salvando..." : "Salvar rascunho"}</Button>}
              <Button type="button" variant="success" onClick={() => save(null, true)} disabled={busy || outputCalculation.invalidStock || outputCalculation.invalidSelection}>{busy ? "Processando..." : form.id && form.status === "CONFIRMED" ? "Salvar e recalcular" : "Finalizar saída"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {detailRow && <OutputDetails row={detailRow} onClose={() => setDetailRow(null)} />}
      {confirmation && <ConfirmModal {...confirmation} busy={busy} onClose={() => setPendingAction(null)} onConfirm={executeAction} />}
    </>
  );
}
