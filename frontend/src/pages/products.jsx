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
  Outra: 2,
};

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
  package_config: null,
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

function defaultUnitsForType(name) {
  return DEFAULT_UNITS_BY_TYPE[name] || 2;
}

export function ProductsPage({ notify, me }) {
  const list = useList("products/", { deleted: "all" });
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [containerTypes, setContainerTypes] = useState([]);
  const [groupingTypes, setGroupingTypes] = useState([]);
  const [newPackagingName, setNewPackagingName] = useState("");
  const [newGroupingName, setNewGroupingName] = useState("");
  const [creatingPackaging, setCreatingPackaging] = useState(false);
  const [creatingGrouping, setCreatingGrouping] = useState(false);
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  async function loadReferences() {
    const [categoriesResult, suppliersResult, containersResult, groupingsResult] = await Promise.allSettled([
      api.get("categories/?page_size=200"),
      api.get("suppliers/?page_size=200"),
      api.get("packaging-types/?page_size=500&kind=CONTAINER"),
      api.get("packaging-types/?page_size=500&kind=GROUPING"),
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

    if (containersResult.status === "fulfilled") {
      setContainerTypes(sortedByName(unwrap(containersResult.value.data)));
    } else {
      setContainerTypes([]);
      notify(`Não foi possível carregar as embalagens: ${getError(containersResult.reason)}`, "error");
    }

    if (groupingsResult.status === "fulfilled") {
      setGroupingTypes(sortedByName(unwrap(groupingsResult.value.data)));
    } else {
      setGroupingTypes([]);
      notify(`Não foi possível carregar os tipos de empacotamento: ${getError(groupingsResult.reason)}`, "error");
    }
  }

  useEffect(() => {
    loadReferences();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function openNewProduct() {
    setNewPackagingName("");
    setNewGroupingName("");
    setForm({ ...productInitial });
  }

  function editProduct(row) {
    if (row.is_deleted) return;
    const options = row.packaging_options || [];
    const selectedGrouping = options.find((option) => option.active && option.is_default)
      || options.find((option) => option.active)
      || options[0]
      || null;

    setNewPackagingName("");
    setNewGroupingName("");
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
      package_config: selectedGrouping ? {
        id: selectedGrouping.id,
        packaging_type: String(selectedGrouping.packaging_type || ""),
        packaging_type_name: selectedGrouping.packaging_type_name || selectedGrouping.name || "Embalagem",
        units_per_package: String(selectedGrouping.units_per_package || 2),
        cost_price: formatMoneyInput(selectedGrouping.cost_price ?? 0),
        sale_price: formatMoneyInput(selectedGrouping.sale_price ?? 0),
      } : null,
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
      const response = await api.post("packaging-types/", {
        name,
        kind: "CONTAINER",
        active: true,
      });
      const created = response.data;
      setContainerTypes((current) => sortedByName([
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

  function chooseGroupingType(typeId) {
    if (!typeId) {
      setForm((current) => ({ ...current, package_config: null }));
      return;
    }

    const type = groupingTypes.find((item) => String(item.id) === String(typeId));
    setForm((current) => {
      const sameType = String(current.package_config?.packaging_type || "") === String(typeId);
      return {
        ...current,
        package_config: {
          ...(sameType ? current.package_config : {}),
          packaging_type: String(typeId),
          packaging_type_name: type?.name || "Empacotamento",
          units_per_package: sameType
            ? current.package_config.units_per_package
            : String(defaultUnitsForType(type?.name)),
          cost_price: sameType ? current.package_config.cost_price : "0,00",
          sale_price: sameType ? current.package_config.sale_price : "0,00",
        },
      };
    });
  }

  function updateGrouping(key, value) {
    setForm((current) => ({
      ...current,
      package_config: current.package_config
        ? { ...current.package_config, [key]: value }
        : null,
    }));
  }

  async function createGroupingType() {
    const name = newGroupingName.trim();
    if (!name) {
      notify("Digite o nome do novo tipo, como Caixa, Fardo ou Grade.", "error");
      return;
    }

    setCreatingGrouping(true);
    try {
      const response = await api.post("packaging-types/", {
        name,
        kind: "GROUPING",
        active: true,
      });
      const created = response.data;
      setGroupingTypes((current) => sortedByName([
        ...current.filter((item) => item.id !== created.id),
        created,
      ]));
      setNewGroupingName("");
      setForm((current) => ({
        ...current,
        package_config: {
          packaging_type: String(created.id),
          packaging_type_name: created.name,
          units_per_package: String(defaultUnitsForType(created.name)),
          cost_price: "0,00",
          sale_price: "0,00",
        },
      }));
      notify(`Tipo “${created.name}” criado e selecionado.`);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setCreatingGrouping(false);
    }
  }

  async function save(event) {
    event.preventDefault();

    if (!form.packaging) {
      notify("Selecione a embalagem do produto.", "error");
      return;
    }

    if (form.package_config) {
      const units = Math.trunc(parseLocalizedNumber(form.package_config.units_per_package));
      if (units < 2) {
        notify(`Informe quantas unidades existem em cada ${form.package_config.packaging_type_name}.`, "error");
        return;
      }
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
      packaging_options: form.package_config ? [{
        ...(form.package_config.id ? { id: Number(form.package_config.id) } : {}),
        packaging_type: Number(form.package_config.packaging_type),
        units_per_package: String(form.package_config.units_per_package),
        cost_price: String(form.package_config.cost_price),
        sale_price: String(form.package_config.sale_price),
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
        detail: [
          blockers ? `Vínculos encontrados: ${blockers}.` : "",
          pendingAction.canDeactivate ? "Você pode inativar o produto." : "O produto já está inativo.",
        ].filter(Boolean).join(" "),
        confirmLabel: pendingAction.canDeactivate ? "Inativar produto" : "Entendi",
        confirmVariant: pendingAction.canDeactivate ? "warning" : "secondary",
      };
    }
    const activate = type === "activate";
    return {
      title: activate ? "Ativar produto" : "Inativar produto",
      message: `${activate ? "Ativar" : "Inativar"} “${row.name}”?`,
      detail: activate
        ? "O produto voltará a ficar disponível."
        : "O produto ficará indisponível para novas operações.",
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

  const groupingName = form?.package_config?.packaging_type_name || "empacotamento";

  return (
    <>
      <PageHeader
        title="Produtos"
        description="Cadastre o produto, sua embalagem individual e, quando houver, o tipo de empacotamento usado na compra ou venda."
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
          {containerTypes.map((packaging) => <option key={packaging.id} value={packaging.id}>{packaging.name}</option>)}
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
            { key: "package_description", label: "Tipo", render: (row) => row.packaging_options?.length ? row.package_description : "Somente unidade" },
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
            <Field label="Categoria" required><select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required><option value="">Selecione a categoria</option>{categories.map((category) => <option key={category.id} value={category.id} disabled={!category.active && Number(form.category) !== category.id}>{category.name}{category.active ? "" : " (inativa)"}</option>)}</select></Field>
            <Field label="Fornecedor principal"><select value={form.supplier || ""} onChange={(event) => setForm({ ...form, supplier: event.target.value })}><option value="">Não informado</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id} disabled={!supplier.active && Number(form.supplier) !== supplier.id}>{supplier.name}{supplier.active ? "" : " (inativo)"}</option>)}</select></Field>

            <Field label="Marca"><input value={form.brand || ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} placeholder="Opcional" /></Field>
            <Field label="Volume de uma unidade" required><input type="number" min="1" step="1" value={form.volume} onChange={(event) => setForm({ ...form, volume: event.target.value })} placeholder="Ex.: 350" required /></Field>
            <Field label="Unidade do volume" required><select value={form.volume_unit} onChange={(event) => setForm({ ...form, volume_unit: event.target.value })} required><option value="ML">Mililitros (ML)</option><option value="L">Litros (L)</option></select></Field>

            <div className="simple-packaging-config full">
              <div className="section-heading compact-heading">
                <div>
                  <h3>Embalagem do produto</h3>
                  <p>É a apresentação física da unidade, como lata, garrafa, garrafa PET ou long neck.</p>
                </div>
              </div>
              <div className="simple-packaging-select-grid">
                <Field label="Embalagem" required>
                  <select value={form.packaging || ""} onChange={(event) => setForm({ ...form, packaging: event.target.value })} required>
                    <option value="">Selecione a embalagem</option>
                    {containerTypes.map((packaging) => <option key={packaging.id} value={packaging.id} disabled={!packaging.active && String(form.packaging) !== String(packaging.id)}>{packaging.name}{packaging.active ? "" : " (inativa)"}</option>)}
                  </select>
                </Field>
                <Field label="Adicionar nova embalagem"><input value={newPackagingName} onChange={(event) => setNewPackagingName(event.target.value)} placeholder="Ex.: GARRAFA DE VIDRO" /></Field>
                <div className="simple-packaging-create"><Button type="button" variant="secondary" icon={Plus} onClick={createPackagingType} disabled={creatingPackaging}>{creatingPackaging ? "Adicionando..." : "Adicionar embalagem"}</Button></div>
              </div>
            </div>

            <Field label="Preço de custo por unidade individual" required><input type="text" inputMode="decimal" value={form.cost_price} onChange={(event) => setForm({ ...form, cost_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, cost_price: formatMoneyInput(current.cost_price) }))} required /></Field>
            <Field label="Preço de venda por unidade individual" required><input type="text" inputMode="decimal" value={form.sale_price} onChange={(event) => setForm({ ...form, sale_price: event.target.value })} onBlur={() => setForm((current) => ({ ...current, sale_price: formatMoneyInput(current.sale_price) }))} required /></Field>
            <Field label="Estoque mínimo em unidades" hint="O sistema avisará quando o saldo atingir ou ficar abaixo deste valor."><input type="number" min="0" step="1" value={form.minimum_stock} onChange={(event) => setForm({ ...form, minimum_stock: event.target.value })} /></Field>

            <div className="simple-packaging-config full">
              <div className="section-heading compact-heading">
                <div>
                  <h3>Tipo de embalagem ou empacotamento</h3>
                  <p>Opcional. Informe se o produto também é comprado ou vendido em caixa, fardo, grade/engradado, pacote ou outro agrupamento.</p>
                </div>
              </div>
              <div className="simple-packaging-select-grid">
                <Field label="Tipo já cadastrado">
                  <select value={form.package_config?.packaging_type || ""} onChange={(event) => chooseGroupingType(event.target.value)}>
                    <option value="">Somente unidade individual</option>
                    {groupingTypes.map((type) => <option key={type.id} value={type.id} disabled={!type.active && String(form.package_config?.packaging_type) !== String(type.id)}>{type.name}{type.active ? "" : " (inativo)"}</option>)}
                  </select>
                </Field>
                <Field label="Cadastrar novo tipo"><input value={newGroupingName} onChange={(event) => setNewGroupingName(event.target.value)} placeholder="Ex.: Caixa, Fardo ou Grade" /></Field>
                <div className="simple-packaging-create"><Button type="button" variant="secondary" icon={Plus} onClick={createGroupingType} disabled={creatingGrouping}>{creatingGrouping ? "Criando..." : "Criar e selecionar"}</Button></div>
              </div>

              {form.package_config ? (
                <div className="simple-packaging-fields">
                  <Field label={`Unidades contidas em cada ${groupingName}`} required><input type="number" min="2" step="1" value={form.package_config.units_per_package} onChange={(event) => updateGrouping("units_per_package", event.target.value)} required /></Field>
                  <Field label={`Preço de custo por ${groupingName}`} required><input type="text" inputMode="decimal" value={form.package_config.cost_price} onChange={(event) => updateGrouping("cost_price", event.target.value)} onBlur={() => updateGrouping("cost_price", formatMoneyInput(form.package_config.cost_price))} required /></Field>
                  <Field label={`Preço de venda por ${groupingName}`} required><input type="text" inputMode="decimal" value={form.package_config.sale_price} onChange={(event) => updateGrouping("sale_price", event.target.value)} onBlur={() => updateGrouping("sale_price", formatMoneyInput(form.package_config.sale_price))} required /></Field>
                  <div className="simple-packaging-preview"><strong>1 {groupingName}</strong><span>= {fmtQty(form.package_config.units_per_package)} unidades individuais</span></div>
                </div>
              ) : <div className="simple-packaging-empty">Este produto será movimentado somente por unidade individual. Selecione um tipo para informar a quantidade e os preços da caixa, fardo, grade ou pacote.</div>}
            </div>

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
