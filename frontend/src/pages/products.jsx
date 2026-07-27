import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  fmtMoney,
  fmtQty,
  formatMoneyInput,
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

const productInitial = {
  name: "",
  category: "",
  supplier: "",
  packaging: "",
  brand: "",
  volume: "500",
  volume_unit: "ML",
  cost_price: "0,00",
  sale_price: "0,00",
  minimum_stock: "0",
  active: true,
};

function productSubtitle(row) {
  const volume = row.volume ? `${row.volume}${row.volume_unit || ""}` : "";
  return [row.brand, volume].filter(Boolean).join(" • ") || row.category_name;
}

function stockLevel(row) {
  if (Number(row.stock) <= 0) return ["out", "Sem estoque"];
  if (row.low_stock) return ["low", "Estoque baixo"];
  return ["normal", "Normal"];
}

function sortedByName(rows) {
  return [...rows].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

export function ProductsPage({ notify, me }) {
  const list = useList("products/", { deleted: "all" });
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [packagingTypes, setPackagingTypes] = useState([]);
  const [newPackagingName, setNewPackagingName] = useState("");
  const [creatingPackaging, setCreatingPackaging] = useState(false);
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  async function loadReferences() {
    const [categoriesResult, suppliersResult, packagingResult] = await Promise.allSettled([
      api.get("categories/?page_size=200"),
      api.get("suppliers/?page_size=200"),
      api.get("packaging-types/?page_size=500"),
    ]);

    if (categoriesResult.status === "fulfilled") {
      setCategories(unwrap(categoriesResult.value.data));
    } else {
      setCategories([]);
      notify(`Não foi possível carregar as categorias: ${getError(categoriesResult.reason)}`, "error");
    }

    if (suppliersResult.status === "fulfilled") {
      setSuppliers(unwrap(suppliersResult.value.data));
    } else {
      setSuppliers([]);
      notify(`Não foi possível carregar os fornecedores: ${getError(suppliersResult.reason)}`, "error");
    }

    if (packagingResult.status === "fulfilled") {
      setPackagingTypes(sortedByName(unwrap(packagingResult.value.data)));
    } else {
      setPackagingTypes([]);
      notify(`Não foi possível carregar as embalagens: ${getError(packagingResult.reason)}`, "error");
    }
  }

  useEffect(() => {
    loadReferences();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function openNewProduct() {
    setNewPackagingName("");
    setForm({ ...productInitial });
  }

  function editProduct(row) {
    if (row.is_deleted) return;
    setNewPackagingName("");
    setForm({
      id: row.id,
      name: row.name || "",
      category: row.category || "",
      supplier: row.supplier || "",
      packaging: row.packaging || "",
      brand: row.brand || "",
      volume: row.volume == null ? "" : String(row.volume),
      volume_unit: row.volume_unit || "ML",
      cost_price: formatMoneyInput(row.cost_price),
      sale_price: formatMoneyInput(row.sale_price),
      minimum_stock: String(row.minimum_stock ?? 0),
      active: Boolean(row.active),
    });
  }

  async function createPackagingType() {
    const name = newPackagingName.trim().toLocaleUpperCase("pt-BR");
    if (!name) {
      notify("Digite o nome da nova embalagem.", "error");
      return;
    }

    setCreatingPackaging(true);
    try {
      const response = await api.post("packaging-types/", { name, active: true });
      const created = response.data;
      setPackagingTypes((current) => sortedByName([
        ...current.filter((item) => item.id !== created.id),
        created,
      ]));
      setForm((current) => ({ ...current, packaging: String(created.id) }));
      setNewPackagingName("");
      notify(`Embalagem “${created.name}” criada e selecionada.`);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setCreatingPackaging(false);
    }
  }

  async function save(event) {
    event.preventDefault();
    if (!form.packaging) {
      notify("Selecione a embalagem do produto.", "error");
      return;
    }

    const payload = {
      name: form.name.trim(),
      description: "",
      category: Number(form.category),
      supplier: form.supplier ? Number(form.supplier) : null,
      packaging: Number(form.packaging),
      brand: form.brand?.trim() || "",
      volume: String(form.volume),
      volume_unit: form.volume_unit,
      unit: "UN",
      package_quantity: "1",
      cost_price: String(form.cost_price),
      sale_price: String(form.sale_price),
      minimum_stock: String(form.minimum_stock),
      active: Boolean(form.active),
      packaging_options: [],
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
        await api.delete(`products/${row.id}/`, {
          data: { reason: "Exclusão solicitada pelo usuário" },
        });
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
          message: data.detail || "Este produto ainda possui vínculos e não pode ser excluído.",
          blockers: data.blockers || [],
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
    if (type === "delete") {
      return {
        title: "Excluir produto",
        message: `Deseja excluir “${row.name}”?`,
        detail: "O produto continuará no histórico quando houver vínculos operacionais.",
        confirmLabel: "Excluir produto",
        confirmVariant: "danger",
      };
    }
    if (type === "blocked") {
      const blockers = (pendingAction.blockers || [])
        .map((item) => typeof item === "string" ? item : item.description || item.label)
        .filter(Boolean)
        .join(", ");
      return {
        title: "Produto protegido pelo histórico",
        message: pendingAction.message,
        detail: [blockers ? `Vínculos encontrados: ${blockers}.` : "", pendingAction.canDeactivate ? "Você pode inativar o produto." : "O produto já está inativo."].filter(Boolean).join(" "),
        confirmLabel: pendingAction.canDeactivate ? "Inativar produto" : "Entendi",
        confirmVariant: pendingAction.canDeactivate ? "warning" : "secondary",
      };
    }
    const activate = type === "activate";
    return {
      title: activate ? "Ativar produto" : "Inativar produto",
      message: `${activate ? "Ativar" : "Inativar"} “${row.name}”?`,
      detail: activate ? "O produto voltará a ficar disponível." : "O produto ficará indisponível para novas operações.",
      confirmLabel: activate ? "Ativar produto" : "Inativar produto",
      confirmVariant: activate ? "success" : "warning",
    };
  })();

  const productStatusFilter = list.params.deleted === "true"
    ? "DELETED"
    : list.params.active === "true"
      ? "ACTIVE"
      : list.params.active === "false" && list.params.deleted !== "all"
        ? "INACTIVE"
        : "";

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

  return (
    <>
      <PageHeader
        title="Produtos"
        description="Cadastre cada produto com sua categoria, embalagem, preços e estoque mínimo."
        actions={me.permissions.is_admin && <Button icon={Plus} onClick={openNewProduct}>Novo produto</Button>}
      />

      <div className="filters-bar">
        <SearchBar
          value={search}
          onChange={(value) => {
            setSearch(value);
            list.setParams({ ...list.params, search: value, page: 1 });
          }}
          placeholder="Nome, marca ou embalagem..."
        />
        <select value={list.params.category || ""} onChange={(event) => list.setParams({ ...list.params, category: event.target.value, page: 1 })}>
          <option value="">Todas as categorias</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        <select value={list.params.packaging || ""} onChange={(event) => list.setParams({ ...list.params, packaging: event.target.value, page: 1 })}>
          <option value="">Todas as embalagens</option>
          {packagingTypes.map((packaging) => <option key={packaging.id} value={packaging.id}>{packaging.name}</option>)}
        </select>
        <select value={productStatusFilter} onChange={(event) => changeProductStatus(event.target.value)}>
          <option value="">Todos os cadastros</option>
          <option value="ACTIVE">Somente ativos</option>
          <option value="INACTIVE">Somente inativos</option>
          <option value="DELETED">Somente excluídos</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          rowClassName={(row) => row.is_deleted ? "row-soft-deleted" : (!row.active ? "inactive-row" : "")}
          columns={[
            {
              key: "name",
              label: "Produto",
              render: (row) => (
                <div className="product-cell">
                  <div className="product-placeholder"><Package size={17} /></div>
                  <span><strong>{row.name}</strong><small>{productSubtitle(row)}</small></span>
                </div>
              ),
            },
            { key: "category_name", label: "Categoria" },
            { key: "packaging_name", label: "Embalagem", render: (row) => <strong>{row.packaging_name || row.package_type || "—"}</strong> },
            { key: "stock", label: "Estoque", render: (row) => <strong>{fmtQty(row.stock)} UN</strong> },
            { key: "minimum_stock", label: "Estoque mínimo", render: (row) => `${fmtQty(row.minimum_stock)} UN` },
            {
              key: "level",
              label: "Nível",
              render: (row) => {
                const [value, label] = stockLevel(row);
                return <StatusBadge value={value} label={label} />;
              },
            },
            { key: "cost_price", label: "Custo", render: (row) => fmtMoney(row.cost_price) },
            { key: "sale_price", label: "Venda", render: (row) => fmtMoney(row.sale_price) },
            {
              key: "active",
              label: "Cadastro",
              render: (row) => row.is_deleted
                ? <StatusBadge value="DELETED" label="Excluído" />
                : <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} />,
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => {
                if (row.is_deleted) return <span className="muted-text">Histórico</span>;
                if (!me.permissions.is_admin) return "—";
                return (
                  <div className="row-actions">
                    <button onClick={() => editProduct(row)} title="Editar produto"><Pencil size={16} /></button>
                    <button className={row.active ? "warning" : "success"} onClick={() => setPendingAction({ type: row.active ? "deactivate" : "activate", row })} title={row.active ? "Inativar produto" : "Ativar produto"}>{row.active ? <PowerOff size={16} /> : <Power size={16} />}</button>
                    <button className="danger" onClick={() => setPendingAction({ type: "delete", row })} title="Excluir produto"><Trash2 size={16} /></button>
                  </div>
                );
              },
            },
          ]}
        />
        <Pagination page={list.params.page} count={list.count} onChange={(page) => list.setParams({ ...list.params, page })} />
      </section>

      {form && (
        <Modal title={form.id ? "Editar produto" : "Novo produto"} onClose={() => setForm(null)} size="xl">
          <form className="form-grid cols-3 product-form-simple" onSubmit={save}>
            <Field label="Nome do produto" required><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Coca-Cola" required /></Field>
            <Field label="Categoria" required><select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required><option value="">Selecione a categoria</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
            <Field label="Fornecedor principal"><select value={form.supplier || ""} onChange={(event) => setForm({ ...form, supplier: event.target.value })}><option value="">Não informado</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></Field>

            <Field label="Marca"><input value={form.brand || ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} placeholder="Opcional" /></Field>
            <Field label="Volume de uma unidade" required><input type="number" min="1" step="1" value={form.volume} onChange={(event) => setForm({ ...form, volume: event.target.value })} placeholder="Ex.: 350" required /></Field>
            <Field label="Unidade do volume" required><select value={form.volume_unit} onChange={(event) => setForm({ ...form, volume_unit: event.target.value })} required><option value="ML">Mililitros (ML)</option><option value="L">Litros (L)</option></select></Field>

            <div className="simple-packaging-config full">
              <div className="section-heading compact-heading">
                <div>
                  <h3>Embalagem</h3>
                  <p>Selecione a embalagem do produto ou cadastre uma nova opção.</p>
                </div>
              </div>
              <div className="simple-packaging-select-grid">
                <Field label="Embalagem do produto" required>
                  <select value={form.packaging || ""} onChange={(event) => setForm({ ...form, packaging: event.target.value })} required>
                    <option value="">Selecione a embalagem</option>
                    {packagingTypes.map((packaging) => <option key={packaging.id} value={packaging.id} disabled={!packaging.active && String(form.packaging) !== String(packaging.id)}>{packaging.name}{packaging.active ? "" : " (inativa)"}</option>)}
                  </select>
                </Field>
                <Field label="Adicionar nova embalagem"><input value={newPackagingName} onChange={(event) => setNewPackagingName(event.target.value)} placeholder="Ex.: GARRAFA DE VIDRO" /></Field>
                <div className="simple-packaging-create"><Button type="button" variant="secondary" icon={Plus} onClick={createPackagingType} disabled={creatingPackaging}>{creatingPackaging ? "Adicionando..." : "Adicionar embalagem"}</Button></div>
              </div>
            </div>

            <Field label="Preço de custo por unidade" required><input type="text" inputMode="decimal" value={form.cost_price} onChange={(event) => setForm({ ...form, cost_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, cost_price: formatMoneyInput(current.cost_price) }))} required /></Field>
            <Field label="Preço de venda por unidade" required><input type="text" inputMode="decimal" value={form.sale_price} onChange={(event) => setForm({ ...form, sale_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, sale_price: formatMoneyInput(current.sale_price) }))} required /></Field>
            <Field label="Estoque mínimo em unidades" hint="O sistema avisará quando o saldo atingir ou ficar abaixo deste valor."><input type="number" min="0" step="1" value={form.minimum_stock} onChange={(event) => setForm({ ...form, minimum_stock: event.target.value })} /></Field>

            <label className="checkbox-line product-active-check"><input type="checkbox" checked={form.active !== false} onChange={(event) => setForm({ ...form, active: event.target.checked })} /><span>Produto disponível para novas operações</span></label>
            <div />
            <div />

            <div className="form-actions full"><Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button><Button>Salvar produto</Button></div>
          </form>
        </Modal>
      )}

      {confirmation && <ConfirmModal {...confirmation} busy={actionBusy} onClose={() => setPendingAction(null)} onConfirm={executePendingAction} />}
    </>
  );
}
