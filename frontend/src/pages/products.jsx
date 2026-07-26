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
  Check,
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

function defaultUnitsForType(typeName) {
  return DEFAULT_UNITS_BY_TYPE[typeName] || 2;
}

function optionTypeName(option, packagingTypes) {
  return option.packaging_type_name
    || packagingTypes.find((type) => String(type.id) === String(option.packaging_type))?.name
    || "Embalagem";
}

const productInitial = {
  name: "",
  description: "",
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
  packaging_options: [],
};

function productSubtitle(row) {
  return [row.brand, row.package_description]
    .filter(Boolean)
    .join(" • ") || row.category_name;
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
  const [creatingPackagingType, setCreatingPackagingType] = useState(false);
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("categories/?page_size=200"),
      api.get("suppliers/?page_size=200"),
      api.get("packaging-types/?page_size=500"),
    ])
      .then(([categoriesResponse, suppliersResponse, packagingTypesResponse]) => {
        setCategories(unwrap(categoriesResponse.data));
        setSuppliers(unwrap(suppliersResponse.data));
        setPackagingTypes(unwrap(packagingTypesResponse.data));
      })
      .catch(() => {
        setCategories([]);
        setSuppliers([]);
        setPackagingTypes([]);
      });
  }, []);

  function editProduct(row) {
    if (row.is_deleted) return;
    setForm({
      id: row.id,
      name: row.name || "",
      description: row.description || "",
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
      packaging_options: (row.packaging_options || []).map((option) => ({
        id: option.id,
        packaging_type: option.packaging_type || "",
        packaging_type_name: option.packaging_type_name || option.name || "Embalagem",
        units_per_package: String(option.units_per_package || 2),
        cost_price: formatMoneyInput(option.cost_price ?? 0),
        sale_price: formatMoneyInput(option.sale_price ?? 0),
        is_default: Boolean(option.is_default),
        active: option.active !== false,
      })),
    });
  }

  async function save(event) {
    event.preventDefault();
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description?.trim() || "",
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
        packaging_options: (form.packaging_options || []).map((option) => ({
          ...(option.id ? { id: Number(option.id) } : {}),
          packaging_type: Number(option.packaging_type),
          units_per_package: String(option.units_per_package),
          cost_price: String(option.cost_price),
          sale_price: String(option.sale_price),
          is_default: Boolean(option.is_default),
          active: option.active !== false,
        })),
      };

      if (form.id) await api.patch(`products/${form.id}/`, payload);
      else await api.post("products/", payload);

      notify("Produto salvo com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  function addPackagingOption(preferredType = null) {
    setForm((current) => {
      const used = new Set((current.packaging_options || []).map((option) => String(option.packaging_type)));
      const selectedType = preferredType
        || packagingTypes.find((type) => type.active && !used.has(String(type.id)))
        || packagingTypes.find((type) => type.active);
      if (!selectedType) {
        notify("Cadastre primeiro um tipo de embalagem, como Caixa, Fardo ou Pacote.", "error");
        return current;
      }
      const units = defaultUnitsForType(selectedType.name);
      const unitCost = parseLocalizedNumber(current.cost_price);
      const unitSale = parseLocalizedNumber(current.sale_price);
      return {
        ...current,
        packaging_options: [
          ...(current.packaging_options || []),
          {
            packaging_type: selectedType.id,
            packaging_type_name: selectedType.name,
            units_per_package: String(units),
            cost_price: formatMoneyInput(unitCost * units),
            sale_price: formatMoneyInput(unitSale),
            is_default: !(current.packaging_options || []).some((option) => option.is_default && option.active !== false),
            active: true,
          },
        ],
      };
    });
  }

  function updatePackagingOption(index, key, value) {
    setForm((current) => ({
      ...current,
      packaging_options: current.packaging_options.map((option, optionIndex) => {
        if (optionIndex !== index) {
          return key === "is_default" && value ? { ...option, is_default: false } : option;
        }
        if (key === "packaging_type") {
          const type = packagingTypes.find((row) => String(row.id) === String(value));
          return {
            ...option,
            packaging_type: value,
            packaging_type_name: type?.name || option.packaging_type_name,
            units_per_package: option.units_per_package || String(defaultUnitsForType(type?.name)),
          };
        }
        return { ...option, [key]: value };
      }),
    }));
  }

  async function createPackagingType() {
    const name = newPackagingType.trim();
    if (!name) {
      notify("Digite o nome do novo tipo de embalagem.", "error");
      return;
    }
    setCreatingPackagingType(true);
    try {
      const response = await api.post("packaging-types/", { name, active: true });
      const created = response.data;
      setPackagingTypes((current) => [...current.filter((item) => item.id !== created.id), created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
      setNewPackagingType("");
      addPackagingOption(created);
      notify(`Tipo de embalagem “${created.name}” criado e adicionado ao produto.`);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setCreatingPackagingType(false);
    }
  }

  function removePackagingOption(index) {
    setForm((current) => ({
      ...current,
      packaging_options: current.packaging_options.filter((_, optionIndex) => optionIndex !== index),
    }));
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
    if (type === "delete") {
      return {
        title: "Excluir produto",
        message: `Deseja excluir “${row.name}”?`,
        detail: "O produto deixará de ser utilizado em novas operações, mas continuará visível em cinza como Excluído para preservar o histórico. A exclusão só será permitida quando não houver estoque nem vínculos operacionais pendentes.",
        confirmLabel: "Excluir produto",
        confirmVariant: "danger",
      };
    }
    if (type === "blocked") {
      const blockerText = (pendingAction.blockers || [])
        .map((item) => typeof item === "string" ? item : item.description || `${item.label}${item.count ? ` (${item.count})` : ""}`)
        .filter(Boolean)
        .join(", ");
      return {
        title: "Produto protegido pelo histórico",
        message: pendingAction.message,
        detail: [
          blockerText ? `Vínculos encontrados: ${blockerText}.` : "",
          pendingAction.canDeactivate
            ? "Você pode inativar o produto. O cadastro deixará de ser usado em novas operações, mas o histórico continuará disponível."
            : "O produto já está inativo e deve permanecer no sistema para preservar a rastreabilidade.",
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
        ? "O produto voltará a ficar disponível para novas operações."
        : "O cadastro e todo o histórico serão preservados, mas o produto deixará de ficar disponível para novas operações.",
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
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => setForm({ ...productInitial })}>
            Novo produto
          </Button>
        )}
      />

      <div className="filters-bar">
        <SearchBar
          value={search}
          onChange={(value) => {
            setSearch(value);
            list.setParams({ ...list.params, search: value, page: 1 });
          }}
          placeholder="Nome, marca ou descrição..."
        />
        <select
          value={list.params.category || ""}
          onChange={(event) => list.setParams({ ...list.params, category: event.target.value, page: 1 })}
        >
          <option value="">Todas as categorias</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}{category.active ? "" : " (inativa)"}
            </option>
          ))}
        </select>
        <select
          value={productStatusFilter}
          onChange={(event) => changeProductStatus(event.target.value)}
        >
          <option value="">Todos os cadastros</option>
          <option value="ACTIVE">Somente ativos</option>
          <option value="INACTIVE">Somente inativos</option>
          <option value="DELETED">Somente excluídos</option>
        </select>
        <select
          value={list.params.stock_level || ""}
          onChange={(event) => list.setParams({ ...list.params, stock_level: event.target.value, page: 1 })}
        >
          <option value="">Todos os níveis de estoque</option>
          <option value="normal">Normal</option>
          <option value="low">Estoque baixo</option>
          <option value="out">Sem estoque</option>
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
                  <span>
                    <strong>{row.name}</strong>
                    <small>{productSubtitle(row)}</small>
                    {row.is_deleted && <small className="muted-text">Mantido somente para histórico</small>}
                  </span>
                </div>
              ),
            },
            { key: "category_name", label: "Categoria" },
            { key: "stock", label: "Estoque", render: (row) => <strong>{fmtQty(row.stock)} UN</strong> },
            {
              key: "active",
              label: "Cadastro",
              render: (row) => row.is_deleted
                ? <StatusBadge value="DELETED" label="Excluído" />
                : <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} />,
            },
            {
              key: "level",
              label: "Nível de estoque",
              render: (row) => {
                if (row.is_deleted) return <StatusBadge value="DELETED" label="Histórico" />;
                const [value, label] = stockLevel(row);
                return <StatusBadge value={value} label={label} />;
              },
            },
            { key: "cost_price", label: "Custo", render: (row) => fmtMoney(row.cost_price) },
            { key: "sale_price", label: "Venda", render: (row) => fmtMoney(row.sale_price) },
            { key: "stock_value", label: "Valor em estoque", render: (row) => fmtMoney(row.stock_value) },
            {
              key: "actions",
              label: "Ações",
              render: (row) => {
                if (row.is_deleted) return <span className="muted-text">Histórico</span>;
                if (!me.permissions.is_admin) return "-";
                return (
                  <div className="row-actions">
                    <button onClick={() => editProduct(row)} title="Editar produto" aria-label={`Editar ${row.name}`}>
                      <Pencil size={16} />
                    </button>
                    <button
                      className={row.active ? "warning" : "success"}
                      onClick={() => setPendingAction({ type: row.active ? "deactivate" : "activate", row })}
                      title={row.active ? "Inativar produto" : "Ativar produto"}
                      aria-label={`${row.active ? "Inativar" : "Ativar"} ${row.name}`}
                    >
                      {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                    </button>
                    <button
                      className="danger"
                      onClick={() => setPendingAction({ type: "delete", row })}
                      title="Excluir produto e manter no histórico"
                      aria-label={`Excluir ${row.name}`}
                    >
                      <Trash2 size={16} />
                    </button>
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
        <Modal title={form.id ? "Editar produto" : "Novo produto"} onClose={() => setForm(null)} size="xl">
          <form className="form-grid cols-3" onSubmit={save}>
            <Field label="Nome do produto" required>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </Field>

            <Field label="Categoria" required>
              <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required>
                <option value="">Selecione</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id} disabled={!category.active && Number(form.category) !== category.id}>
                    {category.name}{category.active ? "" : " (inativa)"}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Fornecedor principal">
              <select value={form.supplier || ""} onChange={(event) => setForm({ ...form, supplier: event.target.value })}>
                <option value="">Não informado</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id} disabled={!supplier.active && Number(form.supplier) !== supplier.id}>
                    {supplier.name}{supplier.active ? "" : " (inativo)"}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Marca">
              <input value={form.brand || ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} />
            </Field>

            <Field label="Volume de cada unidade do produto" required hint="Digite somente o número. Ex.: 1, 350, 500 ou 965.">
              <input
                type="number"
                min="1"
                step="1"
                value={form.volume}
                onChange={(event) => setForm({ ...form, volume: event.target.value })}
                required
              />
            </Field>

            <Field label="Unidade de medida do volume" required>
              <select value={form.volume_unit} onChange={(event) => setForm({ ...form, volume_unit: event.target.value })} required>
                <option value="ML">Mililitros (ML)</option>
                <option value="L">Litros (L)</option>
              </select>
            </Field>

            <Field label="Identificação do volume por unidade">
              <input value={`${form.volume || ""}${form.volume_unit || ""}`} readOnly aria-label="Volume completo de cada unidade" />
            </Field>

            <Field label="Unidade usada no controle do estoque">
              <input value="UN — Unidade individual" readOnly />
            </Field>

            <Field label="Preço de custo por unidade individual" hint="Valor pago por 1 unidade do produto. Aceita vírgula ou ponto.">
              <input
                type="text"
                inputMode="decimal"
                value={form.cost_price}
                onChange={(event) => setForm({ ...form, cost_price: event.target.value })}
                onBlur={() => setForm((current) => ({ ...current, cost_price: formatMoneyInput(current.cost_price) }))}
              />
            </Field>

            <Field label="Preço de venda por unidade individual" hint="Valor cobrado por 1 unidade do produto. Aceita vírgula ou ponto.">
              <input
                type="text"
                inputMode="decimal"
                value={form.sale_price}
                onChange={(event) => setForm({ ...form, sale_price: event.target.value })}
                onBlur={() => setForm((current) => ({ ...current, sale_price: formatMoneyInput(current.sale_price) }))}
              />
            </Field>

            <Field label="Estoque mínimo">
              <input type="number" min="0" step="1" value={form.minimum_stock} onChange={(event) => setForm({ ...form, minimum_stock: event.target.value })} />
            </Field>

            <Field label="Estoque máximo">
              <input type="number" min="0" step="1" value={form.maximum_stock} onChange={(event) => setForm({ ...form, maximum_stock: event.target.value })} />
            </Field>

            <div className="packaging-config full">
              <div className="packaging-config-heading">
                <div>
                  <h3>Formas de entrada e saída do produto</h3>
                  <p>Cadastre como este produto é comprado e vendido. O estoque sempre será convertido e controlado em unidades individuais.</p>
                </div>
                <Button type="button" variant="secondary" icon={Plus} onClick={() => addPackagingOption()}>Adicionar forma de embalagem</Button>
              </div>

              <div className="packaging-default-row">
                <strong>Unidade individual</strong>
                <span>1 unidade no estoque</span>
                <small>Custo {fmtMoney(parseLocalizedNumber(form.cost_price))} • Venda {fmtMoney(parseLocalizedNumber(form.sale_price))}</small>
              </div>

              <div className="packaging-type-create">
                <Field label="Criar novo tipo de embalagem" hint="Ex.: Caixa térmica, Engradado retornável ou Pacote.">
                  <input value={newPackagingType} onChange={(event) => setNewPackagingType(event.target.value)} placeholder="Digite um novo tipo" />
                </Field>
                <Button type="button" variant="secondary" icon={Plus} disabled={creatingPackagingType} onClick={createPackagingType}>
                  {creatingPackagingType ? "Criando..." : "Criar e adicionar"}
                </Button>
              </div>

              {(form.packaging_options || []).map((option, index) => {
                const typeName = optionTypeName(option, packagingTypes);
                const duplicateTypes = new Set((form.packaging_options || []).filter((_, optionIndex) => optionIndex !== index).map((item) => String(item.packaging_type)));
                return (
                  <div className="packaging-option-card" key={option.id || index}>
                    <div className="packaging-option-fields">
                      <Field label="Tipo de embalagem" required>
                        <select value={option.packaging_type || ""} onChange={(event) => updatePackagingOption(index, "packaging_type", event.target.value)} required>
                          <option value="">Selecione o tipo</option>
                          {packagingTypes.map((type) => (
                            <option key={type.id} value={type.id} disabled={duplicateTypes.has(String(type.id)) || (!type.active && String(option.packaging_type) !== String(type.id))}>
                              {type.name}{type.active ? "" : " (inativo)"}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label={`Quantidade de unidades contidas em cada ${typeName}`} required hint={`Ex.: se 1 ${typeName} contém 12 unidades, digite 12.`}>
                        <input type="number" min="2" step="1" value={option.units_per_package} onChange={(event) => updatePackagingOption(index, "units_per_package", event.target.value)} required />
                      </Field>
                      <Field label={`Preço de custo por ${typeName}`} required hint={`Valor pago por 1 ${typeName} completo.`}>
                        <input type="text" inputMode="decimal" value={option.cost_price} onChange={(event) => updatePackagingOption(index, "cost_price", event.target.value)} onBlur={() => updatePackagingOption(index, "cost_price", formatMoneyInput(option.cost_price))} required />
                      </Field>
                      <Field label={`Preço de venda por ${typeName}`} required hint={`Valor cobrado por 1 ${typeName} completo, sem multiplicar novamente pelas unidades.`}>
                        <input type="text" inputMode="decimal" value={option.sale_price} onChange={(event) => updatePackagingOption(index, "sale_price", event.target.value)} onBlur={() => updatePackagingOption(index, "sale_price", formatMoneyInput(option.sale_price))} required />
                      </Field>
                    </div>
                    <div className="packaging-option-footer">
                      <label className="checkbox-line">
                        <input type="checkbox" checked={Boolean(option.is_default)} onChange={(event) => updatePackagingOption(index, "is_default", event.target.checked)} />
                        <span>Usar {typeName} como forma inicial nas novas entradas e saídas</span>
                      </label>
                      <label className="checkbox-line">
                        <input type="checkbox" checked={option.active !== false} onChange={(event) => updatePackagingOption(index, "active", event.target.checked)} />
                        <span>Disponível para novas operações</span>
                      </label>
                      <div className="packaging-conversion-preview">
                        <Check size={16} /> 1 {typeName} = {option.units_per_package || 0} unidades individuais
                      </div>
                      <button type="button" className="icon-btn danger" onClick={() => removePackagingOption(index)} aria-label={`Remover ${typeName}`}><Trash2 size={16} /></button>
                    </div>
                  </div>
                );
              })}
              {!form.packaging_options?.length && <div className="packaging-empty">Nenhuma embalagem adicional cadastrada. Este produto poderá entrar e sair somente como unidade individual.</div>}
            </div>

            <Field label="Descrição">
              <textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </Field>

            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar produto</Button>
            </div>
          </form>
        </Modal>
      )}

      {confirmation && (
        <ConfirmModal
          {...confirmation}
          busy={actionBusy}
          onClose={() => setPendingAction(null)}
          onConfirm={executePendingAction}
        />
      )}
    </>
  );
}
