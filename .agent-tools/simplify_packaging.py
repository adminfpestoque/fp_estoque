from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path, old, new):
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado em {relative_path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Backend: categoria volta a ser somente classificação de produto.
replace_once(
    "backend/inventory/models/catalog.py",
    '    """Catálogo único de formas de embalagem usado por categorias e produtos."""',
    '    """Catálogo de tipos de embalagem usado exclusivamente pelos produtos."""',
)
replace_once(
    "backend/inventory/models/catalog.py",
    '''    packaging_types = models.ManyToManyField(
        PackagingType,
        blank=True,
        related_name="categories",
    )

''',
    "",
)
replace_once(
    "backend/inventory/models/catalog.py",
    '''        if self.product_id and self.packaging_type_id:
            self.product.category.packaging_types.add(self.packaging_type)
''',
    "",
)

replace_once(
    "backend/inventory/serializers/catalog.py",
    '    categories_count = serializers.IntegerField(read_only=True, required=False)\n',
    "",
)
replace_once(
    "backend/inventory/serializers/catalog.py",
    '''class CategorySerializer(serializers.ModelSerializer):
    packaging_types = serializers.PrimaryKeyRelatedField(
        queryset=PackagingType.objects.all(),
        many=True,
        required=False,
    )
    packaging_type_names = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def get_packaging_type_names(self, obj):
        return [item.name for item in obj.packaging_types.all().order_by("name")]
''',
    '''class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
''',
)
replace_once(
    "backend/inventory/serializers/catalog.py",
    '''    def _validate_packaging_options(self, options):
        type_ids = set()
''',
    '''    def _validate_packaging_options(self, options):
        if len(options or []) > 1:
            raise serializers.ValidationError(
                {"packaging_options": "Cadastre somente um tipo de embalagem adicional por produto."}
            )
        type_ids = set()
''',
)
replace_once(
    "backend/inventory/serializers/catalog.py",
    '''        if packaging_options:
            product.category.packaging_types.add(
                *[item["packaging_type"] for item in packaging_options]
            )
            default_option = product.packaging_options.filter(is_default=True).first()
''',
    '''        if packaging_options:
            default_option = product.packaging_options.filter(is_default=True).first()
''',
)
replace_once(
    "backend/inventory/serializers/catalog.py",
    '''            if packaging_options:
                product.category.packaging_types.add(
                    *[item["packaging_type"] for item in packaging_options]
                )
            default_option = product.packaging_options.filter(is_default=True).first()
''',
    '''            default_option = product.packaging_options.filter(is_default=True).first()
''',
)

replace_once(
    "backend/inventory/views/catalog.py",
    '    queryset = Category.objects.prefetch_related("packaging_types").all()\n',
    '    queryset = Category.objects.all()\n',
)
replace_once(
    "backend/inventory/views/catalog.py",
    '''        return PackagingType.objects.annotate(
            products_count=Count("product_options", distinct=True),
            categories_count=Count("categories", distinct=True),
        ).order_by("name")
''',
    '''        return PackagingType.objects.annotate(
            products_count=Count("product_options", distinct=True),
        ).order_by("name")
''',
)
replace_once(
    "backend/inventory/views/catalog.py",
    '''        product_count = packaging_type.product_options.count()
        category_count = packaging_type.categories.count()
        if product_count or category_count:
            return Response(
                {
                    "detail": (
                        "Este tipo de embalagem está sendo usado por produtos ou categorias. "
                        "Remova os vínculos ou inative o tipo para preservar o histórico."
                    ),
                    "products_count": product_count,
                    "categories_count": category_count,
                    "can_deactivate": packaging_type.active,
                },
                status=status.HTTP_409_CONFLICT,
            )
''',
    '''        product_count = packaging_type.product_options.count()
        if product_count:
            return Response(
                {
                    "detail": (
                        "Este tipo de embalagem está sendo usado por produtos. "
                        "Altere os produtos vinculados ou inative o tipo para preservar o histórico."
                    ),
                    "products_count": product_count,
                    "can_deactivate": packaging_type.active,
                },
                status=status.HTTP_409_CONFLICT,
            )
''',
)

migration = ROOT / "backend/inventory/migrations/0012_remove_category_packaging_types.py"
migration.write_text(
    '''from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("inventory", "0011_alter_productpackaging_options_and_more")]

    operations = [
        migrations.RemoveField(
            model_name="category",
            name="packaging_types",
        ),
    ]
''',
    encoding="utf-8",
)

categories_source = r'''import {
  React,
  useState,
  api,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Pencil,
  Plus,
  Power,
  PowerOff,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";

export function CategoriesPage({ notify, me }) {
  const list = useList("categories/");
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);

  function openCategory(row = null) {
    setForm(row ? { ...row } : { name: "", description: "", active: true });
  }

  async function saveCategory(event) {
    event.preventDefault();
    const payload = {
      name: form.name.trim(),
      description: form.description?.trim() || "",
      active: Boolean(form.active),
    };
    setBusy(true);
    try {
      if (form.id) await api.put(`categories/${form.id}/`, payload);
      else await api.post("categories/", payload);
      notify("Categoria salva com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleCategory() {
    if (!pendingAction) return;
    setBusy(true);
    try {
      const activate = !pendingAction.active;
      await api.post(`categories/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      notify(`Categoria ${activate ? "ativada" : "inativada"} com sucesso.`);
      setPendingAction(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Categorias"
        description="Organize os produtos por grupos, como Refrigerantes, Cervejas, Águas e Destilados."
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => openCategory()}>Nova categoria</Button>
        )}
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
          placeholder="Nome ou descrição da categoria..."
        />
        <select
          value={list.params.active ?? ""}
          onChange={(event) => list.setParams({ ...list.params, active: event.target.value, page: 1 })}
        >
          <option value="">Ativas e inativas</option>
          <option value="true">Somente ativas</option>
          <option value="false">Somente inativas</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "name", label: "Categoria", render: (row) => <strong>{row.name}</strong> },
            { key: "description", label: "Descrição", render: (row) => row.description || "—" },
            {
              key: "active",
              label: "Situação",
              render: (row) => <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativa" : "Inativa"} />,
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => openCategory(row)} title="Editar categoria"><Pencil size={16} /></button>
                  <button
                    className={row.active ? "warning" : "success"}
                    onClick={() => setPendingAction(row)}
                    title={row.active ? "Inativar categoria" : "Ativar categoria"}
                  >
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                </div>
              ) : "—",
            },
          ]}
        />
      </section>

      {form && (
        <Modal title={form.id ? "Editar categoria" : "Nova categoria"} onClose={() => !busy && setForm(null)}>
          <form className="form-grid" onSubmit={saveCategory}>
            <Field label="Nome da categoria" required>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Refrigerantes" required />
            </Field>
            <Field label="Descrição da categoria">
              <textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Opcional" />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
              <Button disabled={busy}>{busy ? "Salvando..." : "Salvar categoria"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {pendingAction && (
        <ConfirmModal
          title={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          message={`${pendingAction.active ? "Inativar" : "Ativar"} “${pendingAction.name}”?`}
          detail={pendingAction.active
            ? "A categoria ficará indisponível para novos produtos, mas continuará no histórico."
            : "A categoria voltará a ficar disponível para novos produtos."}
          confirmLabel={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          confirmVariant={pendingAction.active ? "warning" : "success"}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={toggleCategory}
        />
      )}
    </>
  );
}
'''
(ROOT / "frontend/src/pages/categories.jsx").write_text(categories_source, encoding="utf-8")

products_source = r'''import {
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
      choosePackagingType(created.id);
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
'''
(ROOT / "frontend/src/pages/products.jsx").write_text(products_source, encoding="utf-8")

# Entrada e saída: textos e resumos mais diretos, sem blocos redundantes.
documents_path = ROOT / "frontend/src/pages/documents.jsx"
documents = documents_path.read_text(encoding="utf-8")
replacements = {
    'return `Quantidade de embalagens do tipo ${option.name}`;': 'return `Quantidade de ${option.name}`;',
    'return `Preço de custo por ${option.name}`;': 'return `Preço de custo por ${option.name}`;',
    'Registre compras por unidade, caixa, fardo, pacote ou outra embalagem e converta automaticamente para unidades de estoque.': 'Registre os produtos recebidos e o sistema atualizará o estoque em unidades individuais.',
    'Escolha o produto, a forma de retirada e a quantidade. O sistema converte tudo para unidades e calcula o pagamento.': 'Registre vendas e outras retiradas com cálculo automático do estoque e do pagamento.',
    '<div className="checkout-products-heading"><div><h3>Produtos recebidos</h3><p>Escolha a forma recebida. O sistema transforma caixas, fardos e pacotes em unidades reais de estoque.</p></div>': '<div className="checkout-products-heading"><div><h3>Itens da entrada</h3><p>Selecione o produto, a forma recebida e a quantidade.</p></div>',
    'label="Produto recebido"': 'label="Produto"',
    'label="Forma de entrada"': 'label="Recebido em"',
    'hint="Informe quantas unidades ou embalagens foram recebidas."': 'hint="Digite a quantidade da forma selecionada."',
    'hint="Valor pago por cada unidade, caixa, fardo, pacote ou outra forma selecionada."': 'hint="Valor pago por uma unidade da forma selecionada."',
    '<span>Conversão para o estoque</span>': '<span>Entrada no estoque</span>',
    '<small>Custo equivalente por unidade: {fmtMoney(line?.unitCost || 0)}</small>': '',
    'Total de unidades adicionadas:': 'Unidades adicionadas:',
    'Valor total da compra:': 'Total da entrada:',
    '<div className="checkout-products-heading"><div><h3>Produtos da saída</h3><p>Para cada produto: escolha como ele será retirado, informe quantas embalagens ou unidades e confira a baixa real no estoque.</p></div>': '<div className="checkout-products-heading"><div><h3>Itens da saída</h3><p>Selecione o produto, a forma de retirada e a quantidade.</p></div>',
    'label="1. Produto"': 'label="Produto"',
    'label="2. Retirar como"': 'label="Retirar em"',
    'label={`3. Quantidade de ${line?.selected?.name || "Unidade"}`}': 'label={`Quantidade de ${line?.selected?.name || "Unidade"}`}',
    'label="4. Lote"': 'label="Lote (opcional)"',
    '<span>Conversão da retirada</span>': '<span>Baixa no estoque</span>',
    '<small>Equivale a {fmtMoney(line?.unitPrice || 0)} por unidade</small>': '',
    '                <Field label="Observações da saída"><textarea value={form.notes || ""} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></Field>\n': '',
    '<div className="checkout-total-row"><span>Total da saída</span>': '<div className="checkout-total-row"><span>{form.reason === "COMMERCIAL" ? "Total da venda" : "Valor da saída"}</span>',
    '<span>Total de unidades baixadas do estoque</span>': '<span>Unidades retiradas do estoque</span>',
}
for old, new in replacements.items():
    if old not in documents:
        raise RuntimeError(f"Trecho de documents.jsx não encontrado: {old[:100]!r}")
    documents = documents.replace(old, new, 1)
documents_path.write_text(documents, encoding="utf-8")

content_css = ROOT / "frontend/src/styles/content.css"
css = content_css.read_text(encoding="utf-8")
css += r'''

.simple-packaging-config {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px;
  background: var(--surface-soft, #fafafa);
}
.simple-packaging-select-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: end;
}
.simple-packaging-create { display: flex; align-items: end; }
.simple-packaging-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(190px, .8fr);
  gap: 12px;
  align-items: end;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.simple-packaging-preview {
  min-height: 68px;
  border-radius: 11px;
  padding: 12px 14px;
  background: var(--surface, white);
  border: 1px solid var(--border);
  display: grid;
  align-content: center;
  gap: 3px;
}
.simple-packaging-preview strong,
.simple-packaging-preview span { display: block; }
.simple-packaging-preview span { color: var(--muted); font-size: 13px; }
.simple-packaging-empty {
  margin-top: 16px;
  padding: 13px 14px;
  border-radius: 10px;
  border: 1px dashed var(--border);
  color: var(--muted);
}
.product-active-check { align-self: end; min-height: 46px; }
@media (max-width: 900px) {
  .simple-packaging-select-grid,
  .simple-packaging-fields { grid-template-columns: 1fr; }
}
'''
content_css.write_text(css, encoding="utf-8")
