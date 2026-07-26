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

const PACKAGING_TYPES = [
  ["BOX", "Caixa"],
  ["BUNDLE", "Fardo"],
  ["CRATE", "Grade/engradado"],
  ["PACK", "Pacote"],
  ["TRAY", "Bandeja"],
  ["BAG", "Saco"],
  ["OTHER", "Outra"],
];

const productInitial = {
  name: "",
  description: "",
  category: "",
  supplier: "",
  brand: "",
  package_type: "",
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
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("categories/?page_size=200"),
      api.get("suppliers/?page_size=200"),
    ])
      .then(([categoriesResponse, suppliersResponse]) => {
        setCategories(unwrap(categoriesResponse.data));
        setSuppliers(unwrap(suppliersResponse.data));
      })
      .catch(() => {
        setCategories([]);
        setSuppliers([]);
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
      package_type: row.package_type || "",
      volume: row.volume == null ? "" : String(row.volume),
      volume_unit: row.volume_unit || "ML",
      cost_price: formatMoneyInput(row.cost_price),
      sale_price: formatMoneyInput(row.sale_price),
      minimum_stock: String(row.minimum_stock ?? 0),
      maximum_stock: String(row.maximum_stock ?? 0),
      active: Boolean(row.active),
      packaging_options: (row.packaging_options || []).map((option) => ({
        id: option.id,
        type: option.type || "BOX",
        name: option.name || option.type_display || "Caixa",
        units_per_package: String(option.units_per_package || 2),
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
        package_type: form.package_type?.trim() || "",
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
          type: option.type || "OTHER",
          name: option.name?.trim() || "",
          units_per_package: String(option.units_per_package),
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

  function addPackagingOption() {
    setForm((current) => ({
      ...current,
      packaging_options: [
        ...(current.packaging_options || []),
        { type: "BOX", name: "Caixa", units_per_package: "12", active: true },
      ],
    }));
  }

  function updatePackagingOption(index, key, value) {
    setForm((current) => ({
      ...current,
      packaging_options: current.packaging_options.map((option, optionIndex) =>
        optionIndex === index ? { ...option, [key]: value } : option,
      ),
    }));
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

            <Field label="Tipo de embalagem" hint="Ex.: garrafa de vidro, lata ou caixa.">
              <input
                value={form.package_type || ""}
                onChange={(event) => setForm({ ...form, package_type: event.target.value })}
                placeholder="Garrafa de vidro"
              />
            </Field>

            <Field label="Volume" required hint="Digite apenas o número, como 1, 350 ou 500.">
              <input
                type="number"
                min="1"
                step="1"
                value={form.volume}
                onChange={(event) => setForm({ ...form, volume: event.target.value })}
                required
              />
            </Field>

            <Field label="Unidade de medida" required>
              <select value={form.volume_unit} onChange={(event) => setForm({ ...form, volume_unit: event.target.value })} required>
                <option value="ML">Mililitros (ML)</option>
                <option value="L">Litros (L)</option>
              </select>
            </Field>

            <Field label="Apresentação final">
              <input
                value={`${form.package_type ? `${form.package_type.trim()} ` : ""}${form.volume || ""}${form.volume_unit || ""}`}
                readOnly
                aria-label="Apresentação final do produto"
              />
            </Field>

            <Field label="Unidade de estoque">
              <input value="UN" readOnly />
            </Field>

            <Field label="Preço de custo" hint="Aceita vírgula ou ponto.">
              <input
                type="text"
                inputMode="decimal"
                value={form.cost_price}
                onChange={(event) => setForm({ ...form, cost_price: event.target.value })}
                onBlur={() => setForm((current) => ({ ...current, cost_price: formatMoneyInput(current.cost_price) }))}
              />
            </Field>

            <Field label="Preço de venda" hint="Aceita vírgula ou ponto.">
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
                  <h3>Formas de saída do produto</h3>
                  <p>A opção Unidade já existe automaticamente. Cadastre somente caixa, fardo, grade ou pacote e informe quantas unidades existem em cada um.</p>
                </div>
                <Button type="button" variant="secondary" icon={Plus} onClick={addPackagingOption}>Adicionar forma</Button>
              </div>
              <div className="packaging-default-row">
                <strong>Unidade</strong><span>1 UN</span><small>Forma padrão obrigatória</small>
              </div>
              {(form.packaging_options || []).map((option, index) => (
                <div className="packaging-option-row" key={option.id || index}>
                  <Field label="Tipo">
                    <select
                      value={option.type}
                      onChange={(event) => {
                        const label = PACKAGING_TYPES.find(([value]) => value === event.target.value)?.[1] || "Outra";
                        updatePackagingOption(index, "type", event.target.value);
                        if (!option.name || PACKAGING_TYPES.some(([, currentLabel]) => currentLabel === option.name)) {
                          updatePackagingOption(index, "name", label);
                        }
                      }}
                    >
                      {PACKAGING_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                  </Field>
                  <Field label="Nome exibido" required hint="Ex.: Caixa, Grade, Fardo com 6.">
                    <input value={option.name} onChange={(event) => updatePackagingOption(index, "name", event.target.value)} required />
                  </Field>
                  <Field label="Unidades contidas" required>
                    <input type="number" min="2" step="1" value={option.units_per_package} onChange={(event) => updatePackagingOption(index, "units_per_package", event.target.value)} required />
                  </Field>
                  <button type="button" className="icon-btn danger" onClick={() => removePackagingOption(index)} aria-label={`Remover ${option.name || "forma de saída"}`}><Trash2 size={16} /></button>
                </div>
              ))}
              {!form.packaging_options?.length && <div className="packaging-empty">Este produto será retirado somente por unidade até que outra forma seja cadastrada.</div>}
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
