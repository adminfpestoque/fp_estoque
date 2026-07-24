import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  fmtMoney,
  fmtQty,
  fmtDate,
  today,
  getError,
  Button,
  Field,
  DataTable,
  AlertTriangle,
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  BarChart3,
  Boxes,
  CircleDollarSign,
  ClipboardCheck,
  Package,
  RefreshCw,
  X,
} from "../shared.jsx";
import { MetricCard } from "../layout.jsx";

const FILTER_STORAGE_KEY = "fp_dashboard_filters";
const VALID_PERIODS = new Set(["today", "7d", "month", "custom"]);

function defaultFilters() {
  return {
    period: "7d",
    start_date: today(),
    end_date: today(),
    category: "",
    product: "",
  };
}

function loadSavedFilters() {
  const defaults = defaultFilters();

  try {
    const saved = JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) || "null");
    if (!saved || typeof saved !== "object") return defaults;

    return {
      period: VALID_PERIODS.has(saved.period) ? saved.period : defaults.period,
      start_date: saved.start_date || defaults.start_date,
      end_date: saved.end_date || defaults.end_date,
      category: saved.category ? String(saved.category) : "",
      product: saved.product ? String(saved.product) : "",
    };
  } catch {
    return defaults;
  }
}

const asNumber = (value) => Number(value || 0);
const fmtPercent = (value) => `${asNumber(value).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;

export function DashboardPage() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState(loadSavedFilters);
  const [dashboardView, setDashboardView] = useState("sales");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters));
  }, [filters]);

  useEffect(() => {
    let active = true;
    const params = {
      period: filters.period,
      category: filters.category || undefined,
      product: filters.product || undefined,
      ...(filters.period === "custom"
        ? { start_date: filters.start_date, end_date: filters.end_date }
        : {}),
    };

    setLoading(true);
    setError("");
    api
      .get("dashboard/", { params })
      .then((response) => {
        if (active) setData(response.data);
      })
      .catch((requestError) => {
        if (active) setError(getError(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [
    filters.period,
    filters.start_date,
    filters.end_date,
    filters.category,
    filters.product,
  ]);

  const categories = data?.filter_options?.categories || [];
  const allProducts = data?.filter_options?.products || [];
  const availableProducts = useMemo(
    () =>
      filters.category
        ? allProducts.filter((product) => String(product.category_id) === String(filters.category))
        : allProducts,
    [allProducts, filters.category],
  );

  function changeCategory(category) {
    const productStillValid = allProducts.some(
      (product) =>
        String(product.id) === String(filters.product) &&
        (!category || String(product.category_id) === String(category)),
    );
    setFilters((current) => ({
      ...current,
      category,
      product: productStillValid ? current.product : "",
    }));
  }

  function clearFilters() {
    localStorage.removeItem(FILTER_STORAGE_KEY);
    setFilters(defaultFilters());
  }

  if (!data && loading) {
    return <div className="loading"><RefreshCw className="spin" /> Carregando painel...</div>;
  }

  if (!data) {
    return <div className="form-error">{error || "Não foi possível carregar o painel."}</div>;
  }

  const sales = data.sales || {};
  const isSalesView = dashboardView === "sales";

  return (
    <>
      <section className="dashboard-view-switch" aria-label="Escolha a visualização do painel">
        <button
          type="button"
          className={`dashboard-view-option ${isSalesView ? "active" : ""}`}
          onClick={() => setDashboardView("sales")}
          aria-pressed={isSalesView}
        >
          <span className="dashboard-view-icon dashboard-view-icon-sales">
            <CircleDollarSign size={24} />
          </span>
          <span>
            <strong>Desempenho de vendas</strong>
            <small>Vendas, custos, lucro e margem no período escolhido.</small>
          </span>
        </button>

        <button
          type="button"
          className={`dashboard-view-option ${!isSalesView ? "active" : ""}`}
          onClick={() => setDashboardView("stock")}
          aria-pressed={!isSalesView}
        >
          <span className="dashboard-view-icon dashboard-view-icon-stock">
            <Boxes size={24} />
          </span>
          <span>
            <strong>Posição atual do estoque</strong>
            <small>Saldo disponível, valores, potencial de venda e alertas.</small>
          </span>
        </button>
      </section>

      <section className="panel dashboard-filter-panel">
        <div className="dashboard-filter-heading">
          <div>
            <h3>{isSalesView ? "Filtros do desempenho de vendas" : "Filtros da posição de estoque"}</h3>
            <p>
              {isSalesView
                ? "Escolha o período, a categoria ou um produto específico para analisar as vendas."
                : "Escolha uma categoria ou um produto específico para consultar a posição atual do estoque."}
            </p>
          </div>
          <Button type="button" variant="secondary" icon={X} onClick={clearFilters}>
            Limpar filtros
          </Button>
        </div>

        <div className={`dashboard-filter-grid ${!isSalesView ? "dashboard-filter-grid-stock" : ""}`}>
          {isSalesView && (
            <Field label="Período">
              <select
                value={filters.period}
                onChange={(event) => setFilters((current) => ({ ...current, period: event.target.value }))}
              >
                <option value="today">Hoje</option>
                <option value="7d">Últimos 7 dias</option>
                <option value="month">Mês atual</option>
                <option value="custom">Período personalizado</option>
              </select>
            </Field>
          )}

          {isSalesView && filters.period === "custom" && (
            <>
              <Field label="Data inicial">
                <input
                  type="date"
                  value={filters.start_date}
                  onChange={(event) => setFilters((current) => ({ ...current, start_date: event.target.value }))}
                />
              </Field>
              <Field label="Data final">
                <input
                  type="date"
                  value={filters.end_date}
                  onChange={(event) => setFilters((current) => ({ ...current, end_date: event.target.value }))}
                />
              </Field>
            </>
          )}

          <Field label="Categoria">
            <select value={filters.category} onChange={(event) => changeCategory(event.target.value)}>
              <option value="">Todas as categorias</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>{category.name}</option>
              ))}
            </select>
          </Field>

          <Field label="Produto">
            <select
              value={filters.product}
              onChange={(event) => setFilters((current) => ({ ...current, product: event.target.value }))}
            >
              <option value="">Todos os produtos</option>
              {availableProducts.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.code} — {product.name}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="dashboard-scope">
          <span>Analisando:</span>
          <strong>{data.scope?.label || "Todos os produtos"}</strong>
          <small>
            {isSalesView
              ? `Período de ${fmtDate(data.period.start, false)} até ${fmtDate(data.period.end, false)}`
              : "Posição atual, independentemente do período de vendas"}
          </small>
          {loading && <RefreshCw className="spin" size={16} />}
        </div>
      </section>

      {error && <div className="form-error dashboard-request-error">{error}</div>}

      {isSalesView ? (
        <div className="dashboard-view-content" key="sales-panel">
          <div className="dashboard-section-heading">
            <div>
              <h3>Resumo de vendas e rentabilidade</h3>
              <p>Resultado comercial do produto ou da categoria selecionada.</p>
            </div>
          </div>

          <div className="metrics-grid dashboard-business-metrics">
            <MetricCard
              label="Quantidade vendida"
              value={fmtQty(sales.quantity_sold)}
              icon={ArrowUpFromLine}
              tone="gold"
              detail="Unidades retiradas para comercialização"
            />
            <MetricCard
              label="Valor vendido"
              value={fmtMoney(sales.revenue)}
              icon={CircleDollarSign}
              tone="success"
              detail="Quantidade × preço de venda"
            />
            <MetricCard
              label="Custo dos produtos vendidos"
              value={fmtMoney(sales.cost)}
              icon={ArrowDownToLine}
              detail="Custo registrado nas movimentações"
            />
            <MetricCard
              label="Lucro bruto"
              value={fmtMoney(sales.gross_profit)}
              icon={BarChart3}
              tone={asNumber(sales.gross_profit) >= 0 ? "success" : "danger"}
              detail="Valor vendido menos custo"
            />
            <MetricCard
              label="Margem bruta"
              value={fmtPercent(sales.margin_percent)}
              icon={BarChart3}
              tone="gold"
              detail="Percentual do lucro sobre as vendas"
            />
            <MetricCard
              label="Vendas registradas"
              value={sales.sales_documents || 0}
              icon={ClipboardCheck}
              detail="Saídas comerciais confirmadas"
            />
          </div>

          <section className="panel dashboard-performance-panel">
            <div className="panel-title dashboard-panel-title">
              <div>
                <h3>Resultado comercial por produto</h3>
                <p>Compare custo, preço, quantidade vendida, faturamento, lucro e margem.</p>
              </div>
              <small>Exibindo até 30 produtos</small>
            </div>
            <DataTable
              rows={data.product_performance || []}
              emptyText="Nenhum produto encontrado para os filtros selecionados."
              columns={[
                {
                  key: "name",
                  label: "Produto",
                  render: (row) => (
                    <div className="dashboard-product-name">
                      <strong>{row.name}</strong>
                      <small>{row.code}</small>
                    </div>
                  ),
                },
                { key: "category", label: "Categoria" },
                { key: "unit_cost", label: "Custo unitário", render: (row) => fmtMoney(row.unit_cost) },
                { key: "unit_sale_price", label: "Preço de venda", render: (row) => fmtMoney(row.unit_sale_price) },
                { key: "quantity_sold", label: "Quantidade vendida", render: (row) => fmtQty(row.quantity_sold) },
                { key: "revenue", label: "Valor vendido", render: (row) => fmtMoney(row.revenue) },
                { key: "profit", label: "Lucro bruto", render: (row) => <strong>{fmtMoney(row.profit)}</strong> },
                { key: "margin_percent", label: "Margem", render: (row) => fmtPercent(row.margin_percent) },
              ]}
            />
          </section>

        </div>
      ) : (
        <div className="dashboard-view-content" key="stock-panel">
          <div className="dashboard-section-heading">
            <div>
              <h3>Resumo da posição atual do estoque</h3>
              <p>Quantidade disponível, valores estimados e situações que exigem atenção.</p>
            </div>
          </div>

          <div className="metrics-grid dashboard-stock-metrics">
            <MetricCard
              label="Estoque disponível"
              value={fmtQty(sales.current_stock)}
              icon={Boxes}
              tone="gold"
              detail="Quantidade atual do filtro"
            />
            <MetricCard
              label="Valor do estoque a custo"
              value={fmtMoney(sales.current_stock_cost)}
              icon={CircleDollarSign}
              detail="Estoque × custo atual"
            />
            <MetricCard
              label="Potencial de venda"
              value={fmtMoney(sales.current_stock_sale)}
              icon={CircleDollarSign}
              tone="success"
              detail="Estoque × preço de venda"
            />
            <MetricCard
              label="Lucro potencial do estoque"
              value={fmtMoney(sales.stock_profit_potential)}
              icon={BarChart3}
              tone="success"
              detail="Potencial de venda menos custo"
            />
            <MetricCard
              label="Produtos analisados"
              value={data.products}
              icon={Package}
            />
            <MetricCard
              label="Estoque baixo"
              value={data.low_stock}
              icon={AlertTriangle}
              tone="warning"
            />
            <MetricCard
              label="Sem estoque"
              value={data.out_of_stock}
              icon={Archive}
              tone="danger"
            />
            <MetricCard
              label="Próximos do vencimento"
              value={data.expiring}
              icon={ClipboardCheck}
              tone="warning"
            />
          </div>

          <section className="panel dashboard-performance-panel">
            <div className="panel-title dashboard-panel-title">
              <div>
                <h3>Posição atual por produto</h3>
                <p>Consulte quantidade, custo, valor de venda e lucro potencial de cada produto.</p>
              </div>
              <small>Exibindo até 30 produtos</small>
            </div>
            <DataTable
              rows={data.product_performance || []}
              emptyText="Nenhum produto encontrado para os filtros selecionados."
              columns={[
                {
                  key: "name",
                  label: "Produto",
                  render: (row) => (
                    <div className="dashboard-product-name">
                      <strong>{row.name}</strong>
                      <small>{row.code}</small>
                    </div>
                  ),
                },
                { key: "category", label: "Categoria" },
                { key: "current_stock", label: "Estoque atual", render: (row) => <strong>{fmtQty(row.current_stock)}</strong> },
                { key: "unit_cost", label: "Custo unitário", render: (row) => fmtMoney(row.unit_cost) },
                { key: "stock_cost_value", label: "Valor a custo", render: (row) => fmtMoney(row.stock_cost_value) },
                { key: "unit_sale_price", label: "Preço de venda", render: (row) => fmtMoney(row.unit_sale_price) },
                { key: "stock_sale_value", label: "Potencial de venda", render: (row) => fmtMoney(row.stock_sale_value) },
                { key: "stock_profit_potential", label: "Lucro potencial", render: (row) => <strong>{fmtMoney(row.stock_profit_potential)}</strong> },
              ]}
            />
          </section>

        </div>
      )}
    </>
  );
}
