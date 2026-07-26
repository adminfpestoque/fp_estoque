import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  fmtMoney,
  fmtQty,
  formatMoneyInput,
  parseLocalizedNumber,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  Pagination,
  DataTable,
  StatusBadge,
  Package,
  Pencil,
  Plus,
  Power,
  PowerOff,
  Trash2,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";

const DEFAULT_UNITS_BY_TYPE = {
  Caixa: 12,
  Fardo: 6,
  "Grade/engradado": 24,
  Grade: 24,
  Engradado: 24,
  Pacote: 6,
  Bandeja: 12,
  Saco: 10,
};

const productInitial = {
  name: "",
  category: "",
  supplier: "",
  brand: "",
  volume: "500",
  volume_unit: "ML",
  cost_price: "0,00",
  sale_price: "0,00",
  minimum_stock: "0",
  maximum_stock: "0",
  active: true,
  packaging: null,
};

function defaultUnitsForType(name) {
  return DEFAULT_UNITS_BY_TYPE[name] || 2;
}

function productSubtitle(row) {
  return [row.brand, row.package_description].filter(Boolean).join(" • ") || row.category_name;
}

function stockLevel(row) {
  if (Number(row.stock) <= 0) return ["out", "Sem estoque"];
  if (row.low_stock) return ["low", "Estoque baixo"];
  return ["normal", "Normal"];
}

export function ProductsPage({ notify, me }) {
  const list = useList("products/", { deleted: "all" });
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [packagingTypes, setPackagingTypes] = useState([]);
  const [newPackagingType, setNewPackagingType] = useState("");
  const [creatingType, setCreatingType] = useState(false);
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  async function loadReferences() {
    try {
      const [categoriesResponse, suppliersResponse, packagingResponse] = await Promise.all([
        api.get("categories/?page_size=200"),
        api.get("suppliers/?page_size=200"),
        api.get("packaging-types/?page_size=500"),
      ]);
      setCategories(unwrap(categoriesResponse.data));
      setSuppliers(unwrap(suppliersResponse.data));
      setPackagingTypes(unwrap(packagingResponse.data).sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  useEffect(() => { loadReferences(); }, []);

  function openNewProduct() {
    setNewPackagingType("");
    setForm({ ...productInitial });
  }

  function editProduct(row) {
    if (row.is_deleted) return;
    const options = row.packaging_options || [];
    const selected = options.find((option) => option.active && option.is_default)
      || options.find((option) => option.active)
      || options[0]
      || null;
    setNewPackagingType("");
    setForm({
      id: row.id,
      name: row.name || "",
      category: row.category || "",
      supplier: row.supplier || "",
      brand: row.brand || "",
      volume: row.volume == null ? "" : String(row.volume),
      volume_unit: row.volume_unit || "ML",
      cost_price: formatMoneyInput(row.cost_price),
      sale_price: formatMoneyInput(row.sale_price),
      minimum_stock: String(row.minimum_stock ?? 0),
      maximum_stock: String(row.maximum_stock ?? 0),
      active: Boolean(row.active),
      packaging: selected ? {
        id: selected.id,
        packaging_type: String(selected.packaging_type || ""),
        packaging_type_name: selected.packaging_type_name || selected.name || "Embalagem",
        units_per_package: String(selected.units_per_package || 2),
        cost_price: formatMoneyInput(selected.cost_price ?? 0),
        sale_price: formatMoneyInput(selected.sale_price ?? 0),
      } : null,
    });
  }

  function choosePackagingType(typeId) {
    if (!typeId) {
      setForm((current) => ({ ...current, packaging: null }));
      return;
    }
    const type = packagingTypes.find((item) => String(item.id) === String(typeId));
    setForm((current) => {
      const sameType = String(current.packaging?.packaging_type || "") === String(typeId);
      return {
        ...current,
        packaging: {
          ...(sameType ? current.packaging : {}),
          packaging_type: String(typeId),
          packaging_type_name: type?.name || "Embalagem",
          units_per_package: sameType
            ? current.packaging.units_per_package
            : String(defaultUnitsForType(type?.name)),
          cost_price: sameType ? current.packaging.cost_price : "0,00",
          sale_price: sameType ? current.packaging.sale_price : "0,00",
        },
      };
    });
  }

  function updatePackaging(key, value) {
    setForm((current) => ({
      ...current,
      packaging: current.packaging ? { ...current.packaging, [key]: value } : null,
    }));
  }

  async function createPackagingType() {
    const name = newPackagingType.trim();
    if (!name) {
      notify("Digite o nome do novo tipo de embalagem.", "error");
      return;
    }
    setCreatingType(true);
    try {
      const response = await api.post("packaging-types/", { name, active: true });
      const created = response.data;
      setPackagingTypes((current) => [...current.filter((item) => item.id !== created.id), created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
      setNewPackagingType("");
      setForm((current) => ({
        ...current,
        packaging: {
          packaging_type: String(created.id),
          packaging_type_name: created.name,
          units_per_package: String(defaultUnitsForType(created.name)),
          cost_price: "0,00",
          sale_price: "0,00",
        },
      }));
      notify(`Tipo de embalagem “${created.name}” criado e selecionado.`);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setCreatingType(false);
    }
  }

  async function save(event) {
    event.preventDefault();
    if (form.packaging) {
      const units = Math.trunc(parseLocalizedNumber(form.packaging.units_per_package));
      if (units < 2) {
        notify(`Informe quantas unidades existem em cada ${form.packaging.packaging_type_name}.`, "error");
        return;
      }
    }
    const payload = {
      name: form.name.trim(),
      description: "",
      category: Number(form.category),
      supplier: form.supplier ? Number(form.supplier) : null,
      brand: form.brand?.trim() || "",
      volume: String(form.volume),
      volume_unit: form.volume_unit,
      unit: "UN",
      package_quantity: "1",
      cost_price: String(form.cost_price),
      sale_price: String(form.sale_price),
      minimum_stock: String(form.minimum_stock),
      maximum_stock: String(form.maximum_stock),
      active: Boolean(form.active),
      packaging_options: form.packaging ? [{
        ...(form.packaging.id ? { id: Number(form.packaging.id) } : {}),
        packaging_type: Number(form.packaging.packaging_type),
        units_per_package: String(form.packaging.units_per_package),
        cost_price: String(form.packaging.cost_price),
        sale_price: String(form.packaging.sale_price),
        is_default: true,
        active: true,
      }] : [],
    };
    try {
      if (form.id) await api.patch(`products/${form.id}/`, payload);
      else await api.post("products/", payload);
      notify("Produto salvo com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function executePendingAction() {
    if (!pendingAction) return;
    const { type, row } = pendingAction;
    setActionBusy(true);
    try {
      if (type === "delete") {
        await api.delete(`products/${row.id}/`, { data: { reason: "Exclusão solicitada pelo usuário" } });
        notify("Produto excluído do uso operacional e mantido no histórico.");
      } else if (type === "blocked" && !pendingAction.canDeactivate) {
        setPendingAction(null);
        return;
      } else {
        const activate = type === "activate";
        await api.post(`products/${row.id}/${activate ? "activate" : "deactivate"}/`);
        notify(`Produto ${activate ? "ativado" : "inativado"} com sucesso.`);
      }
      setPendingAction(null);
      list.reload();
    } catch (error) {
      if (type === "delete" && error?.response?.status === 409) {
        const data = error.response.data || {};
        setPendingAction({
          type: "blocked",
          row,
          message: data.detail || "Este produto ainda possui vínculos operacionais e não pode ser excluído.",
          blockers: data.blockers || data.vinculos || [],
          canDeactivate: data.can_deactivate ?? row.active,
        });
      } else {
        notify(getError(error), "error");
      }
    } finally {
      setActionBusy(false);
    }
  }

  const confirmation = pendingAction && (() => {
    const { type, row } = pendingAction;
    if (type === "delete") return {
      title: "Excluir produto",
      message: `Deseja excluir “${row.name}”?`,
      detail: "O produto continuará visível em cinza para preservar o histórico. A exclusão só será permitida quando não houver estoque nem vínculos operacionais pendentes.",
      confirmLabel: "Excluir produto",
      confirmVariant: "danger",
    };
    if (type === "blocked") {
      const blockerText = (pendingAction.blockers || []).map((item) => typeof item === "string" ? item : item.description || `${item.label}${item.count ? ` (${item.count})` : ""}`).filter(Boolean).join(", ");
      return {
        title: "Produto protegido pelo histórico",
        message: pendingAction.message,
        detail: [blockerText ? `Vínculos encontrados: ${blockerText}.` : "", pendingAction.canDeactivate ? "Você pode inativar o produto para impedir novas operações." : "O produto já está inativo e permanece somente para rastreabilidade."].filter(Boolean).join(" "),
        confirmLabel: pendingAction.canDeactivate ? "Inativar produto" : "Entendi",
        confirmVariant: pendingAction.canDeactivate ? "warning" : "secondary",
      };
    }
    const activate = type === "activate";
    return {
      title: activate ? "Ativar produto" : "Inativar produto",
      message: `${activate ? "Ativar" : "Inativar"} “${row.name}”?`,
      detail: activate ? "O produto voltará a ficar disponível para novas operações." : "O cadastro e o histórico serão preservados, mas o produto ficará indisponível para novas operações.",
      confirmLabel: activate ? "Ativar produto" : "Inativar produto",
      confirmVariant: activate ? "success" : "warning",
    };
  })();

  const productStatusFilter = list.params.deleted === "true" ? "DELETED" : list.params.active === "true" ? "ACTIVE" : list.params.active === "false" && list.params.deleted !== "all" ? "INACTIVE" : "";

  function changeProductStatus(value) {
    const next = { ...list.params, page: 1 };
    if (value === "DELETED") {
      next.deleted = "true";
      delete next.active;
    } else if (value === "ACTIVE") {
      next.deleted = "false";
      next.active = "true";
    } else if (value === "INACTIVE") {
      next.deleted = "false";
      next.active = "false";
    } else {
      next.deleted = "all";
      delete next.active;
    }
    list.setParams(next);
  }

  const packagingName = form?.packaging?.packaging_type_name || "embalagem";

  return (
    <>
      <PageHeader
        actions={me.permissions.is_admin && <Button icon={Plus} onClick={openNewProduct}>Novo produto</Button>}
      />

      <div className="filters-bar">
        <SearchBar value={search} onChange={(value) => { setSearch(value); list.setParams({ ...list.params, search: value, page: 1 }); }} placeholder="Nome ou marca..." />
        <select value={list.params.category || ""} onChange={(event) => list.setParams({ ...list.params, category: event.target.value, page: 1 })}>
          <option value="">Todas as categorias</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}{category.active ? "" : " (inativa)"}</option>)}
        </select>
        <select value={productStatusFilter} onChange={(event) => changeProductStatus(event.target.value)}>
          <option value="">Todos os cadastros</option><option value="ACTIVE">Somente ativos</option><option value="INACTIVE">Somente inativos</option><option value="DELETED">Somente excluídos</option>
        </select>
        <select value={list.params.stock_level || ""} onChange={(event) => list.setParams({ ...list.params, stock_level: event.target.value, page: 1 })}>
          <option value="">Todos os níveis de estoque</option><option value="normal">Normal</option><option value="low">Estoque baixo</option><option value="out">Sem estoque</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          rowClassName={(row) => row.is_deleted ? "row-soft-deleted" : (!row.active ? "inactive-row" : "")}
          columns={[
            { key: "name", label: "Produto", render: (row) => <div className="product-cell"><div className="product-placeholder"><Package size={17} /></div><span><strong>{row.name}</strong><small>{productSubtitle(row)}</small>{row.is_deleted && <small className="muted-text">Mantido somente para histórico</small>}</span></div> },
            { key: "category_name", label: "Categoria" },
            { key: "stock", label: "Estoque", render: (row) => <strong>{fmtQty(row.stock)} UN</strong> },
            { key: "active", label: "Cadastro", render: (row) => row.is_deleted ? <StatusBadge value="DELETED" label="Excluído" /> : <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} /> },
            { key: "level", label: "Nível de estoque", render: (row) => { if (row.is_deleted) return <StatusBadge value="DELETED" label="Histórico" />; const [value, label] = stockLevel(row); return <StatusBadge value={value} label={label} />; } },
            { key: "cost_price", label: "Custo unitário", render: (row) => fmtMoney(row.cost_price) },
            { key: "sale_price", label: "Venda unitária", render: (row) => fmtMoney(row.sale_price) },
            { key: "stock_value", label: "Valor em estoque", render: (row) => fmtMoney(row.stock_value) },
            { key: "actions", label: "Ações", render: (row) => {
              if (row.is_deleted) return <span className="muted-text">Histórico</span>;
              if (!me.permissions.is_admin) return "—";
              return <div className="row-actions"><button onClick={() => editProduct(row)} title="Editar produto"><Pencil size={16} /></button><button className={row.active ? "warning" : "success"} onClick={() => setPendingAction({ type: row.active ? "deactivate" : "activate", row })} title={row.active ? "Inativar produto" : "Ativar produto"}>{row.active ? <PowerOff size={16} /> : <Power size={16} />}</button><button className="danger" onClick={() => setPendingAction({ type: "delete", row })} title="Excluir produto"><Trash2 size={16} /></button></div>;
            } },
          ]}
        />
        <Pagination page={list.params.page} count={list.count} onChange={(page) => list.setParams({ ...list.params, page })} />
      </section>

      {form && (
        <Modal title={form.id ? "Editar produto" : "Novo produto"} onClose={() => setForm(null)} size="xl">
          <form className="form-grid cols-3 product-form-simple" onSubmit={save}>
            <Field label="Nome do produto" required><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Coca-Cola lata" required /></Field>
            <Field label="Categoria do produto" required><select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required><option value="">Selecione a categoria</option>{categories.map((category) => <option key={category.id} value={category.id} disabled={!category.active && Number(form.category) !== category.id}>{category.name}{category.active ? "" : " (inativa)"}</option>)}</select></Field>
            <Field label="Fornecedor principal"><select value={form.supplier || ""} onChange={(event) => setForm({ ...form, supplier: event.target.value })}><option value="">Não informado</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id} disabled={!supplier.active && Number(form.supplier) !== supplier.id}>{supplier.name}{supplier.active ? "" : " (inativo)"}</option>)}</select></Field>
            <Field label="Marca"><input value={form.brand || ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} placeholder="Opcional" /></Field>
            <Field label="Volume de uma unidade" required><input type="number" min="1" step="1" value={form.volume} onChange={(event) => setForm({ ...form, volume: event.target.value })} placeholder="Ex.: 350" required /></Field>
            <Field label="Unidade de medida do volume" required><select value={form.volume_unit} onChange={(event) => setForm({ ...form, volume_unit: event.target.value })} required><option value="ML">Mililitros (ML)</option><option value="L">Litros (L)</option></select></Field>

            <Field label="Preço de custo por unidade individual" required><input type="text" inputMode="decimal" value={form.cost_price} onChange={(event) => setForm({ ...form, cost_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, cost_price: formatMoneyInput(current.cost_price) }))} required /></Field>
            <Field label="Preço de venda por unidade individual" required><input type="text" inputMode="decimal" value={form.sale_price} onChange={(event) => setForm({ ...form, sale_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, sale_price: formatMoneyInput(current.sale_price) }))} required /></Field>
            <div />

            <div className="simple-packaging-config full">
              <div className="section-heading compact-heading"><div><h3>Tipo de embalagem ou empacotamento</h3><p>Opcional. Selecione como este produto também pode ser comprado ou vendido além da unidade individual.</p></div></div>
              <div className="simple-packaging-select-grid">
                <Field label="Tipo já cadastrado"><select value={form.packaging?.packaging_type || ""} onChange={(event) => choosePackagingType(event.target.value)}><option value="">Somente unidade individual</option>{packagingTypes.map((type) => <option key={type.id} value={type.id} disabled={!type.active && String(form.packaging?.packaging_type) !== String(type.id)}>{type.name}{type.active ? "" : " (inativo)"}</option>)}</select></Field>
                <Field label="Cadastrar novo tipo"><input value={newPackagingType} onChange={(event) => setNewPackagingType(event.target.value)} placeholder="Ex.: Caixa, Fardo ou Pacote" /></Field>
                <div className="simple-packaging-create"><Button type="button" variant="secondary" icon={Plus} onClick={createPackagingType} disabled={creatingType}>{creatingType ? "Criando..." : "Criar e selecionar"}</Button></div>
              </div>

              {form.packaging ? (
                <div className="simple-packaging-fields">
                  <Field label={`Unidades contidas em cada ${packagingName}`} required><input type="number" min="2" step="1" value={form.packaging.units_per_package} onChange={(event) => updatePackaging("units_per_package", event.target.value)} required /></Field>
                  <Field label={`Preço de custo por ${packagingName}`} required><input type="text" inputMode="decimal" value={form.packaging.cost_price} onChange={(event) => updatePackaging("cost_price", event.target.value)} onBlur={() => updatePackaging("cost_price", formatMoneyInput(form.packaging.cost_price))} required /></Field>
                  <Field label={`Preço de venda por ${packagingName}`} required><input type="text" inputMode="decimal" value={form.packaging.sale_price} onChange={(event) => updatePackaging("sale_price", event.target.value)} onBlur={() => updatePackaging("sale_price", formatMoneyInput(form.packaging.sale_price))} required /></Field>
                  <div className="simple-packaging-preview"><strong>1 {packagingName}</strong><span>= {fmtQty(form.packaging.units_per_package)} unidades individuais</span></div>
                </div>
              ) : <div className="simple-packaging-empty">Este produto será movimentado somente por unidade individual. Os preços da embalagem serão liberados após selecionar ou criar um tipo.</div>}
            </div>

            <Field label="Estoque mínimo"><input type="number" min="0" step="1" value={form.minimum_stock} onChange={(event) => setForm({ ...form, minimum_stock: event.target.value })} /></Field>
            <Field label="Estoque máximo"><input type="number" min="0" step="1" value={form.maximum_stock} onChange={(event) => setForm({ ...form, maximum_stock: event.target.value })} /></Field>
            <label className="checkbox-line product-active-check"><input type="checkbox" checked={form.active !== false} onChange={(event) => setForm({ ...form, active: event.target.checked })} /><span>Produto disponível para novas operações</span></label>

            <div className="form-actions full"><Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button><Button>Salvar produto</Button></div>
          </form>
        </Modal>
      )}

      {confirmation && <ConfirmModal {...confirmation} busy={actionBusy} onClose={() => setPendingAction(null)} onConfirm={executePendingAction} />}
    </>
  );
}
