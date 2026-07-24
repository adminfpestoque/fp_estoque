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
  Modal,
  Field,
  Pagination,
  DataTable,
  StatusBadge,
  Package,
  Pencil,
  Plus,
  Trash2,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";

const productInitial = {
  code: "",
  sku: "",
  barcode: "",
  name: "",
  description: "",
  category: "",
  supplier: "",
  brand: "",
  package_type: "",
  unit: "UN",
  package_quantity: "1",
  cost_price: "0,00",
  sale_price: "0,00",
  minimum_stock: "0",
  maximum_stock: "0",
  location: "",
  image_url: "",
  active: true,
};

export function ProductsPage({ notify, me }) {
  const list = useList("products/");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [form, setForm] = useState(null);

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
    setForm({
      ...row,
      category: row.category,
      supplier: row.supplier || "",
      sku: row.sku || "",
      barcode: row.barcode || "",
      package_quantity: String(row.package_quantity ?? 1),
      cost_price: formatMoneyInput(row.cost_price),
      sale_price: formatMoneyInput(row.sale_price),
      minimum_stock: String(row.minimum_stock ?? 0),
      maximum_stock: String(row.maximum_stock ?? 0),
    });
  }

  async function save(event) {
    event.preventDefault();
    try {
      const payload = {
        ...form,
        code: form.code.trim(),
        sku: form.sku.trim() || null,
        barcode: form.barcode.trim() || null,
        category: Number(form.category),
        supplier: form.supplier ? Number(form.supplier) : null,
        package_quantity: String(form.package_quantity),
        cost_price: String(form.cost_price),
        sale_price: String(form.sale_price),
        minimum_stock: String(form.minimum_stock),
        maximum_stock: String(form.maximum_stock),
      };
      if (form.id) await api.put(`products/${form.id}/`, payload);
      else await api.post("products/", payload);
      notify("Produto salvo com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function deactivate(row) {
    if (!window.confirm(`Inativar ${row.name}?`)) return;
    try {
      await api.delete(`products/${row.id}/`);
      notify("Produto inativado.");
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function uploadImage(file) {
    if (!file) return;
    const payload = new FormData();
    payload.append("image", file);
    try {
      const response = await api.post("uploads/product-image/", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setForm((current) => ({ ...current, image_url: response.data.url }));
      notify("Imagem enviada ao Supabase Storage.");
    } catch (error) {
      notify(getError(error), "error");
    }
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
          placeholder="Nome, código, SKU, código de barras..."
        />
        <select
          value={list.params.category || ""}
          onChange={(event) => list.setParams({ ...list.params, category: event.target.value, page: 1 })}
        >
          <option value="">Todas as categorias</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        <select
          value={list.params.stock_level || ""}
          onChange={(event) => list.setParams({ ...list.params, stock_level: event.target.value, page: 1 })}
        >
          <option value="">Todos os níveis</option>
          <option value="normal">Normal</option>
          <option value="low">Estoque baixo</option>
          <option value="out">Sem estoque</option>
        </select>
      </div>
      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "code", label: "Código" },
            {
              key: "name",
              label: "Produto",
              render: (row) => (
                <div className="product-cell">
                  {row.image_url
                    ? <img src={row.image_url} alt="" />
                    : <div className="product-placeholder"><Package size={17} /></div>}
                  <span><strong>{row.name}</strong><small>{row.brand || row.category_name}</small></span>
                </div>
              ),
            },
            { key: "category_name", label: "Categoria" },
            { key: "stock", label: "Estoque", render: (row) => <strong>{fmtQty(row.stock)} {row.unit}</strong> },
            {
              key: "level",
              label: "Situação",
              render: (row) => (
                <StatusBadge
                  value={Number(row.stock) <= 0 ? "out" : row.low_stock ? "low" : "normal"}
                  label={Number(row.stock) <= 0 ? "Sem estoque" : row.low_stock ? "Estoque baixo" : "Normal"}
                />
              ),
            },
            { key: "cost_price", label: "Custo", render: (row) => fmtMoney(row.cost_price) },
            { key: "stock_value", label: "Valor", render: (row) => fmtMoney(row.stock_value) },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => editProduct(row)} aria-label={`Editar ${row.name}`}><Pencil size={16} /></button>
                  <button className="danger" onClick={() => deactivate(row)} aria-label={`Inativar ${row.name}`}><Trash2 size={16} /></button>
                </div>
              ) : "-",
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
            <Field label="Código interno" required><input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} required /></Field>
            <Field label="SKU"><input value={form.sku || ""} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></Field>
            <Field label="Código de barras"><input value={form.barcode || ""} onChange={(event) => setForm({ ...form, barcode: event.target.value })} /></Field>
            <Field label="Nome" required><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></Field>
            <Field label="Categoria" required>
              <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required>
                <option value="">Selecione</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </Field>
            <Field label="Fornecedor principal">
              <select value={form.supplier || ""} onChange={(event) => setForm({ ...form, supplier: event.target.value })}>
                <option value="">Não informado</option>
                {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
              </select>
            </Field>
            <Field label="Marca"><input value={form.brand || ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></Field>
            <Field label="Tipo de embalagem"><input value={form.package_type || ""} onChange={(event) => setForm({ ...form, package_type: event.target.value })} /></Field>
            <Field label="Unidade"><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value.toUpperCase() })} /></Field>
            <Field label="Quantidade por embalagem">
              <input type="number" min="1" step="1" value={form.package_quantity} onChange={(event) => setForm({ ...form, package_quantity: event.target.value })} />
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
            <Field label="Estoque mínimo"><input type="number" min="0" step="1" value={form.minimum_stock} onChange={(event) => setForm({ ...form, minimum_stock: event.target.value })} /></Field>
            <Field label="Estoque máximo"><input type="number" min="0" step="1" value={form.maximum_stock} onChange={(event) => setForm({ ...form, maximum_stock: event.target.value })} /></Field>
            <Field label="Localização"><input value={form.location || ""} onChange={(event) => setForm({ ...form, location: event.target.value })} /></Field>
            <Field label="Imagem do produto">
              <input type="file" accept="image/*" onChange={(event) => uploadImage(event.target.files?.[0])} />
              <input type="url" value={form.image_url || ""} onChange={(event) => setForm({ ...form, image_url: event.target.value })} placeholder="URL gerada ou imagem externa" />
            </Field>
            <Field label="Descrição"><textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
            <Field label="Situação">
              <select value={String(form.active)} onChange={(event) => setForm({ ...form, active: event.target.value === "true" })}>
                <option value="true">Ativo</option>
                <option value="false">Inativo</option>
              </select>
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar produto</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
