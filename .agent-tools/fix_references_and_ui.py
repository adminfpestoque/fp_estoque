from pathlib import Path

products = Path('frontend/src/pages/products.jsx')
text = products.read_text(encoding='utf-8')
old = '''  async function loadReferences() {
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
'''
new = '''  async function loadReferences() {
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
      setPackagingTypes(
        unwrap(packagingResult.value.data).sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
      );
    } else {
      setPackagingTypes([]);
      notify("Os produtos e as categorias foram carregados, mas os tipos de embalagem ainda não estão disponíveis no backend.", "error");
    }
  }
'''
if old not in text:
    raise SystemExit('loadReferences block not found')
products.write_text(text.replace(old, new), encoding='utf-8')

checkout = Path('frontend/src/styles/checkout.css')
css = checkout.read_text(encoding='utf-8')
addition = r'''

/* Refinamento visual dos formulários de produto, entrada e saída */
.simple-packaging-config {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 15px;
  background: var(--surface-subtle);
  color: var(--text);
  display: grid;
  gap: 14px;
}
.simple-packaging-config .section-heading { margin: 0; }
.simple-packaging-config .section-heading h3 { color: var(--text); }
.simple-packaging-select-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(260px, 1.25fr) auto;
  align-items: end;
  gap: 12px;
}
.simple-packaging-create { display: flex; align-items: end; }
.simple-packaging-create .btn { white-space: nowrap; }
.simple-packaging-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr)) minmax(190px, .8fr);
  gap: 12px;
  align-items: end;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}
.simple-packaging-preview,
.simple-packaging-empty {
  min-height: 70px;
  padding: 12px 14px;
  border: 1px dashed var(--border);
  border-radius: 11px;
  background: var(--surface);
  color: var(--muted);
  display: grid;
  align-content: center;
  gap: 3px;
}
.simple-packaging-preview strong { color: var(--text); font-size: 16px; }

.document-form,
.checkout-form {
  gap: 20px;
}
.document-form > .form-grid:first-child,
.checkout-main > .form-grid:first-child {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-subtle);
}
.checkout-products-heading {
  padding: 2px 2px 10px;
  border-bottom: 1px solid var(--border);
  align-items: center;
}
.checkout-products-heading h3 { font-size: 18px; color: var(--text); }
.checkout-products-heading p { max-width: 680px; }
.checkout-item-card {
  padding: 16px;
  border-left: 4px solid var(--gold);
  box-shadow: 0 6px 18px rgba(0,0,0,.08);
}
.checkout-item-fields .field > span,
.entry-item-fields .field > span {
  font-size: 12px;
  line-height: 1.25;
}
.checkout-item-fields .field > small,
.entry-item-fields .field > small {
  line-height: 1.35;
}
.checkout-item-summary {
  border: 1px solid var(--border);
  min-width: 0;
}
.checkout-item-summary > strong:last-of-type { color: var(--text); }
.checkout-conversion-equation {
  background: var(--surface-subtle);
  border-color: var(--border);
}
.entry-total-summary {
  position: sticky;
  bottom: 0;
  z-index: 3;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: var(--sticky-surface, var(--surface));
  box-shadow: 0 -8px 24px rgba(0,0,0,.08);
}
.entry-total-summary > span {
  background: var(--surface);
  color: var(--text);
}
.checkout-summary {
  border-top: 4px solid var(--gold);
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
}
.checkout-summary-title strong { font-size: 17px; }
.checkout-stock-note { border-left: 4px solid var(--gold); }
.checkout-actions {
  margin-top: 4px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 13px;
}

:root[data-theme="dark"] .simple-packaging-config,
:root[data-theme="dark"] .document-form > .form-grid:first-child,
:root[data-theme="dark"] .checkout-main > .form-grid:first-child,
:root[data-theme="dark"] .entry-total-summary,
:root[data-theme="contrast"] .simple-packaging-config,
:root[data-theme="contrast"] .document-form > .form-grid:first-child,
:root[data-theme="contrast"] .checkout-main > .form-grid:first-child,
:root[data-theme="contrast"] .entry-total-summary {
  background: var(--surface-subtle);
  color: var(--text);
}

@media (max-width: 1100px) {
  .simple-packaging-select-grid,
  .simple-packaging-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .simple-packaging-create { align-self: end; }
}
@media (max-width: 720px) {
  .simple-packaging-select-grid,
  .simple-packaging-fields { grid-template-columns: 1fr; }
  .simple-packaging-create .btn { width: 100%; }
  .checkout-item-card,
  .entry-item-card { padding: 13px; }
  .entry-total-summary { position: static; }
}
'''
if '/* Refinamento visual dos formulários de produto, entrada e saída */' not in css:
    checkout.write_text(css + addition, encoding='utf-8')
