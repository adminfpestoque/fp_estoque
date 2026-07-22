import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  today,
  getError,
  Logo,
  Button,
  Field,
  EmptyState,
  DataTable,
  FileDown,
  FileText,
  Eye,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";

export function ReportsPage({ notify }) {
  const [catalog, setCatalog] = useState([]);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [users, setUsers] = useState([]);
  const [lots, setLots] = useState([]);
  const [filters, setFilters] = useState({
    type: "daily_movements",
    date: today(),
    start_date: "",
    end_date: "",
    product: "",
    category: "",
    supplier: "",
    movement_type: "",
    user: "",
    lot: "",
    stock_status: "",
    brand: "",
  });
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("reports/"),
      api.get("products/?page_size=500"),
      api.get("categories/?page_size=200"),
      api.get("suppliers/?page_size=500"),
      api.get("users/?page_size=500").catch(() => ({ data: [] })),
      api.get("lots/?page_size=500"),
    ]).then(([reports, productData, categoryData, supplierData, userData, lotData]) => {
      setCatalog(reports.data);
      setProducts(unwrap(productData.data));
      setCategories(unwrap(categoryData.data));
      setSuppliers(unwrap(supplierData.data));
      setUsers(unwrap(userData.data));
      setLots(unwrap(lotData.data));
    });
  }, []);

  async function generate() {
    setLoading(true);
    try {
      const response = await api.get("reports/preview/", { params: filters });
      setPreview(response.data);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setLoading(false);
    }
  }

  async function download(format) {
    try {
      const response = await api.get(`reports/export.${format}`, {
        params: filters,
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${filters.type}-${today()}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <>
      <PageHeader
        actions={
          <>
            <Button
              variant="secondary"
              icon={FileDown}
              onClick={() => download("xlsx")}
              disabled={!preview}
            >
              Baixar Excel
            </Button>
            <Button icon={FileText} onClick={() => download("pdf")} disabled={!preview}>
              Baixar PDF
            </Button>
          </>
        }
      />

      <section className="panel report-filters">
        <div className="form-grid cols-4">
          <Field label="Relatório">
            <select
              value={filters.type}
              onChange={(event) => setFilters({ ...filters, type: event.target.value })}
            >
              {catalog.map((report) => (
                <option key={report.id} value={report.id}>{report.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Data específica">
            <input
              type="date"
              value={filters.date}
              onChange={(event) => setFilters({ ...filters, date: event.target.value, start_date: "", end_date: "" })}
            />
          </Field>
          <Field label="Data inicial">
            <input
              type="date"
              value={filters.start_date}
              onChange={(event) => setFilters({ ...filters, start_date: event.target.value, date: "" })}
            />
          </Field>
          <Field label="Data final">
            <input
              type="date"
              value={filters.end_date}
              onChange={(event) => setFilters({ ...filters, end_date: event.target.value, date: "" })}
            />
          </Field>
          <Field label="Produto">
            <select value={filters.product} onChange={(event) => setFilters({ ...filters, product: event.target.value })}>
              <option value="">Todos</option>
              {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
            </select>
          </Field>
          <Field label="Categoria">
            <select value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value })}>
              <option value="">Todas</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </Field>
          <Field label="Fornecedor">
            <select value={filters.supplier} onChange={(event) => setFilters({ ...filters, supplier: event.target.value })}>
              <option value="">Todos</option>
              {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
            </select>
          </Field>
          <Field label="Tipo de movimentação">
            <select value={filters.movement_type} onChange={(event) => setFilters({ ...filters, movement_type: event.target.value })}>
              <option value="">Todos</option>
              <option value="ENTRY">Entrada</option>
              <option value="OUTPUT">Saída</option>
              <option value="ADJ_IN">Ajuste positivo</option>
              <option value="ADJ_OUT">Ajuste negativo</option>
              <option value="REV_IN">Estorno positivo</option>
              <option value="REV_OUT">Estorno negativo</option>
            </select>
          </Field>
          <Field label="Usuário">
            <select value={filters.user} onChange={(event) => setFilters({ ...filters, user: event.target.value })}>
              <option value="">Todos</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>{user.profile?.full_name || user.username}</option>
              ))}
            </select>
          </Field>
          <Field label="Lote">
            <select value={filters.lot} onChange={(event) => setFilters({ ...filters, lot: event.target.value })}>
              <option value="">Todos</option>
              {lots.map((lot) => <option key={lot.id} value={lot.id}>{lot.product_name} — {lot.number}</option>)}
            </select>
          </Field>
          <Field label="Marca">
            <input value={filters.brand} onChange={(event) => setFilters({ ...filters, brand: event.target.value })} placeholder="Todas" />
          </Field>
          <Field label="Situação do estoque">
            <select value={filters.stock_status} onChange={(event) => setFilters({ ...filters, stock_status: event.target.value })}>
              <option value="">Todas</option>
              <option value="normal">Normal</option>
              <option value="low">Estoque baixo</option>
              <option value="out">Sem estoque</option>
            </select>
          </Field>
          <div className="form-actions align-end">
            <Button icon={Eye} onClick={generate} disabled={loading}>
              {loading ? "Gerando..." : "Visualizar"}
            </Button>
          </div>
        </div>
      </section>

      {preview && (
        <section className="panel report-preview">
          <div className="report-preview-head">
            <div>
              <Logo />
              <h3>{preview.title}</h3>
              <p>Período: {preview.period} • Gerado em {preview.generated_at} por {preview.generated_by}</p>
            </div>
          </div>
          {preview.summary && (
            <div className="summary-cards">
              {Object.entries(preview.summary).map(([key, value]) => (
                <div key={key}>
                  <small>{key.replaceAll("_", " ")}</small>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          )}
          {preview.empty_message ? (
            <EmptyState title="Sem dados no período" text={preview.empty_message} />
          ) : (
            <DataTable
              rows={preview.rows}
              columns={
                preview.report_type === "daily_movements"
                  ? [
                    { key: "time", label: "Data/hora" },
                    { key: "type", label: "Tipo" },
                    { key: "product", label: "Produto" },
                    { key: "code", label: "Código" },
                    { key: "lot", label: "Lote" },
                    { key: "previous", label: "Anterior" },
                    { key: "quantity", label: "Movimentada" },
                    { key: "final", label: "Final" },
                    { key: "total", label: "Valor" },
                    { key: "user", label: "Responsável" },
                  ]
                  : preview.columns.map((label, index) => ({
                    key: String(index),
                    label,
                    render: (row) => row[index],
                  }))
              }
              rowKey={preview.report_type === "daily_movements" ? "time" : "_row"}
            />
          )}
        </section>
      )}
    </>
  );
}
