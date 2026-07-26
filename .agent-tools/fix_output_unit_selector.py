from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}')
    return text.replace(old, new, 1)


page_path = Path('frontend/src/pages/documents.jsx')
text = page_path.read_text(encoding='utf-8')

text = replace_once(
    text,
    '''function saleUnitOptions(product) {
  if (!product) return [{ id: "", name: "Unidade", factor: 1 }];
  return [
    { id: "", name: "Unidade", factor: 1 },
    ...(product.packaging_options || [])
      .filter((option) => option.active)
      .map((option) => ({
        id: String(option.id),
        name: option.name,
        factor: Number(option.units_per_package),
      })),
  ];
}''',
    '''function saleUnitOptions(product) {
  const unitOption = {
    id: "",
    name: "Unidade",
    factor: 1,
    description: "Cada quantidade representa 1 unidade do estoque",
  };
  if (!product) return [unitOption];
  return [
    unitOption,
    ...(product.packaging_options || [])
      .filter((option) => option.active && Number(option.units_per_package) > 1)
      .map((option) => ({
        id: String(option.id),
        name: option.name || option.type_display || "Embalagem",
        factor: Number(option.units_per_package),
        description: `Cada ${option.name || option.type_display || "embalagem"} contém ${Number(option.units_per_package)} unidades`,
      })),
  ];
}''',
    'opções de retirada',
)

text = replace_once(
    text,
    '''  const outputItem = {
    product: "",
    packaging: "",
    sale_unit_text: "Unidade",
    sale_quantity: "1",
    lot: "",
    notes: "",
  };''',
    '''  const outputItem = {
    product: "",
    packaging: "",
    sale_quantity: "1",
    lot: "",
    notes: "",
  };''',
    'item inicial de saída',
)

text = replace_once(
    text,
    '''          : {
              packaging: item.packaging || "",
              sale_unit_text: item.sale_unit_name || "Unidade",
              sale_quantity: String(item.sale_quantity || item.quantity || 1),
            }),''',
    '''          : {
              packaging: item.packaging || "",
              sale_quantity: String(item.sale_quantity || item.quantity || 1),
            }),''',
    'edição de item de saída',
)

text = replace_once(
    text,
    '''          ? { ...item, product: productId, packaging: "", sale_unit_text: "Unidade", lot: "" }
          : item,''',
    '''          ? { ...item, product: productId, packaging: "", sale_quantity: "1", lot: "" }
          : item,''',
    'troca de produto',
)

text = replace_once(
    text,
    '''  function changeSaleUnit(index, text) {
    const item = form.items[index];
    const product = products.find((row) => String(row.id) === String(item.product));
    const option = saleUnitOptions(product).find(
      (row) => row.name.toLocaleLowerCase("pt-BR") === text.trim().toLocaleLowerCase("pt-BR"),
    );
    setForm((current) => ({
      ...current,
      items: current.items.map((row, itemIndex) =>
        itemIndex === index
          ? {
              ...row,
              sale_unit_text: text,
              packaging: option ? option.id : row.packaging,
            }
          : row,
      ),
    }));
  }

  function normalizeSaleUnit(index) {
    const item = form.items[index];
    const product = products.find((row) => String(row.id) === String(item.product));
    const options = saleUnitOptions(product);
    const selected = options.find((row) => String(row.id) === String(item.packaging)) || options[0];
    updateItem(index, "sale_unit_text", selected.name);
  }''',
    '''  function changeSaleUnit(index, packagingId) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, packaging: packagingId || "", sale_quantity: item.sale_quantity || "1" }
          : item,
      ),
    }));
  }''',
    'seleção da forma de retirada',
)

text = replace_once(
    text,
    '''  const outputCalculation = useMemo(() => {
    if (!form || isEntry) return { lines: [], total: 0, received: 0, change: 0, missing: 0, invalidStock: false };
    const productTotals = new Map();
    const lines = form.items.map((item) => {
      const product = products.find((row) => String(row.id) === String(item.product));
      const options = saleUnitOptions(product);
      const selected = options.find((row) => String(row.id) === String(item.packaging)) || options[0];
      const saleQuantity = Math.max(0, Math.trunc(parseLocalizedNumber(item.sale_quantity)));
      const stockQuantity = saleQuantity * selected.factor;
      const unitPrice = parseLocalizedNumber(product?.sale_price);
      const subtotal = stockQuantity * unitPrice;
      if (product) productTotals.set(product.id, (productTotals.get(product.id) || 0) + stockQuantity);
      return { product, selected, saleQuantity, stockQuantity, unitPrice, subtotal };
    });
    const total = lines.reduce((sum, line) => sum + line.subtotal, 0);
    const received = parseLocalizedNumber(form.amount_received);
    const change = form.payment_method === "CASH" ? Math.max(received - total, 0) : 0;
    const missing = form.payment_method === "CASH" ? Math.max(total - received, 0) : 0;
    const invalidStock = [...productTotals.entries()].some(([productId, quantity]) => {
      const product = products.find((row) => row.id === productId);
      return quantity > parseLocalizedNumber(product?.stock);
    });
    return { lines, total, received, change, missing, invalidStock };
  }, [form, isEntry, products]);''',
    '''  const outputCalculation = useMemo(() => {
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
      const options = saleUnitOptions(product);
      const selected = options.find((row) => String(row.id) === String(item.packaging));
      if (item.packaging && !selected) invalidSelection = true;
      const effectiveOption = selected || options[0];
      const saleQuantity = Math.max(0, Math.trunc(parseLocalizedNumber(item.sale_quantity)));
      const stockQuantity = saleQuantity * effectiveOption.factor;
      const unitPrice = parseLocalizedNumber(product?.sale_price);
      const subtotal = stockQuantity * unitPrice;
      const currentStock = parseLocalizedNumber(product?.stock);
      const alreadySelected = product ? (productTotals.get(product.id) || 0) : 0;
      const cumulativeQuantity = alreadySelected + stockQuantity;
      if (product) productTotals.set(product.id, cumulativeQuantity);
      return {
        product,
        selected: effectiveOption,
        saleQuantity,
        stockQuantity,
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
  }, [form, isEntry, products]);''',
    'cálculo da saída',
)

text = replace_once(
    text,
    '''    if (!isEntry) {
      if (outputCalculation.invalidStock) {
        notify("A quantidade informada supera o estoque disponível de um dos produtos.", "error");
        return;
      }''',
    '''    if (!isEntry) {
      if (outputCalculation.invalidSelection) {
        notify("Selecione novamente a forma de retirada de um dos produtos.", "error");
        return;
      }
      if (outputCalculation.invalidStock) {
        notify("A quantidade informada supera o estoque disponível de um dos produtos.", "error");
        return;
      }''',
    'validação de seleção',
)

text = replace_once(
    text,
    '''            : "Venda por unidade, caixa, fardo, grade ou pacote, com pagamento e cálculo de troco."''',
    '''            : "Escolha o produto, a forma de retirada e a quantidade. O sistema converte tudo para unidades e calcula o pagamento."''',
    'descrição da página',
)

text = replace_once(
    text,
    '''                <div className="checkout-products-heading"><div><h3>Produtos da saída</h3><p>Escolha primeiro a forma de retirada. O estoque sempre será baixado em unidades.</p></div><Button type="button" variant="secondary" icon={Plus} onClick={() => setForm({ ...form, items: [...form.items, { ...outputItem }] })}>Adicionar produto</Button></div>''',
    '''                <div className="checkout-products-heading"><div><h3>Produtos da saída</h3><p>Para cada produto: escolha como ele será retirado, informe quantas embalagens ou unidades e confira a baixa real no estoque.</p></div><Button type="button" variant="secondary" icon={Plus} onClick={() => setForm({ ...form, items: [...form.items, { ...outputItem }] })}>Adicionar produto</Button></div>''',
    'orientação dos produtos',
)

text = replace_once(
    text,
    '''                          <Field label="Produto" required><select value={item.product || ""} onChange={(event) => changeOutputProduct(index, event.target.value)} required><option value="">Selecione o produto</option>{products.filter((row) => row.active || String(row.id) === String(item.product)).map((row) => <option key={row.id} value={row.id}>{row.name} — {fmtQty(row.stock)} UN disponíveis</option>)}</select></Field>
                          <Field label="Forma de retirada" required hint={product ? `Opções configuradas para ${product.name}` : "Selecione o produto primeiro"}><input list={`sale-unit-${index}`} value={item.sale_unit_text || "Unidade"} onChange={(event) => changeSaleUnit(index, event.target.value)} onBlur={() => normalizeSaleUnit(index)} disabled={!product} required /><datalist id={`sale-unit-${index}`}>{options.map((option) => <option key={option.id || "unit"} value={option.name}>{option.factor === 1 ? "1 unidade" : `${option.factor} unidades`}</option>)}</datalist></Field>
                          <Field label={`Quantidade em ${line?.selected?.name || "Unidade"}`} required><input type="number" min="1" step="1" value={item.sale_quantity} onChange={(event) => updateItem(index, "sale_quantity", event.target.value)} required /></Field>
                          <Field label="Lote" hint="Opcional: automático por validade (FEFO)."><select value={item.lot || ""} onChange={(event) => updateItem(index, "lot", event.target.value)} disabled={!product}><option value="">Automático — FEFO</option>{lots.filter((lot) => String(lot.product) === String(item.product) && (Number(lot.quantity) > 0 || String(lot.id) === String(item.lot))).map((lot) => <option key={lot.id} value={lot.id}>{lot.number} — {fmtQty(lot.quantity)} UN — {lot.expiration_date || "sem validade"}</option>)}</select></Field>''',
    '''                          <Field label="1. Produto" required><select value={item.product || ""} onChange={(event) => changeOutputProduct(index, event.target.value)} required><option value="">Selecione o produto</option>{products.filter((row) => row.active || String(row.id) === String(item.product)).map((row) => <option key={row.id} value={row.id}>{row.name} — {fmtQty(row.stock)} unidades disponíveis</option>)}</select></Field>
                          <Field
                            label="2. Retirar como"
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
                          <Field label={`3. Quantidade de ${line?.selected?.name || "Unidade"}`} required hint="Informe quantas unidades, caixas, fardos ou grades serão retirados."><input type="number" min="1" step="1" value={item.sale_quantity} onChange={(event) => updateItem(index, "sale_quantity", event.target.value)} required /></Field>
                          <Field label="4. Lote" hint="Opcional: o sistema usa primeiro o lote que vence antes."><select value={item.lot || ""} onChange={(event) => updateItem(index, "lot", event.target.value)} disabled={!product}><option value="">Automático por validade</option>{lots.filter((lot) => String(lot.product) === String(item.product) && (Number(lot.quantity) > 0 || String(lot.id) === String(item.lot))).map((lot) => <option key={lot.id} value={lot.id}>{lot.number} — {fmtQty(lot.quantity)} unidades — {lot.expiration_date || "sem validade"}</option>)}</select></Field>''',
    'campos da forma de retirada',
)

text = replace_once(
    text,
    '''                        <div className="checkout-item-summary">
                          <span>{line?.saleQuantity || 0} × {line?.selected?.name || "Unidade"}</span>
                          <strong>{fmtQty(line?.stockQuantity || 0)} UN</strong>
                          <small>Baixa no estoque</small>
                          <span>{fmtMoney(line?.unitPrice || 0)} por UN</span>
                          <strong>{fmtMoney(line?.subtotal || 0)}</strong>
                          {lineInsufficient && <small className="checkout-error">Estoque insuficiente</small>}
                        </div>''',
    '''                        <div className="checkout-item-summary">
                          <span>Conversão da retirada</span>
                          <strong>{fmtQty(line?.saleQuantity || 0)} {line?.selected?.name || "Unidade"}</strong>
                          <div className="checkout-conversion-equation">
                            <span>{fmtQty(line?.saleQuantity || 0)} × {fmtQty(line?.selected?.factor || 1)}</span>
                            <b>=</b>
                            <strong>{fmtQty(line?.stockQuantity || 0)} unidades</strong>
                          </div>
                          <small>Estoque: {fmtQty(line?.currentStock || 0)} → {fmtQty(line?.remainingStock || 0)} unidades</small>
                          <span>{fmtMoney(line?.unitPrice || 0)} por unidade</span>
                          <strong>{fmtMoney(line?.subtotal || 0)}</strong>
                          {lineInsufficient && <small className="checkout-error">Estoque insuficiente</small>}
                        </div>''',
    'resumo da conversão',
)

text = replace_once(
    text,
    '''disabled={busy || outputCalculation.invalidStock}''',
    '''disabled={busy || outputCalculation.invalidStock || outputCalculation.invalidSelection}''',
    'bloqueio do botão',
)

page_path.write_text(text, encoding='utf-8')

style_path = Path('frontend/src/styles/checkout.css')
style = style_path.read_text(encoding='utf-8')
style += '''

/* Seleção clara e visual da forma de retirada */
.checkout-conversion-equation {
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: center;
  justify-content: end;
  gap: 7px;
  margin: 5px 0;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface);
}
.checkout-conversion-equation b {
  color: var(--gold-dark);
  font-size: 16px;
}
.checkout-conversion-equation strong {
  font-size: 15px;
}
@media (max-width: 800px) {
  .checkout-conversion-equation { justify-content: start; }
}
'''
style_path.write_text(style, encoding='utf-8')
