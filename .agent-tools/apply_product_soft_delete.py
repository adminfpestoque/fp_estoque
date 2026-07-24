from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado: {label}")
    return text.replace(old, new, 1)


def replace_section(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Início não encontrado: {label}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Fim não encontrado: {label}")
    return text[:start] + replacement + text[end:]


# Modelo de produto
path = Path("backend/inventory/models/catalog.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from django.db import models\n",
    "from django.conf import settings\nfrom django.db import models\n",
    "import settings no catálogo",
)
text = replace_once(
    text,
    "    image_url = models.URLField(blank=True)\n    active = models.BooleanField(default=True)\n\n    class Meta:",
    "    image_url = models.URLField(blank=True)\n"
    "    active = models.BooleanField(default=True)\n"
    "    deleted_at = models.DateTimeField(null=True, blank=True)\n"
    "    deleted_by = models.ForeignKey(\n"
    "        settings.AUTH_USER_MODEL,\n"
    "        on_delete=models.PROTECT,\n"
    "        null=True,\n"
    "        blank=True,\n"
    "        related_name=\"deleted_products\",\n"
    "    )\n"
    "    deletion_reason = models.TextField(blank=True)\n\n"
    "    class Meta:",
    "campos de exclusão lógica do produto",
)
text = replace_once(
    text,
    "    @property\n    def package_description(self):\n",
    "    @property\n"
    "    def is_deleted(self):\n"
    "        return self.deleted_at is not None\n\n"
    "    @property\n"
    "    def display_status(self):\n"
    "        if self.is_deleted:\n"
    "            return \"Excluído\"\n"
    "        return \"Ativo\" if self.active else \"Inativo\"\n\n"
    "    @property\n"
    "    def package_description(self):\n",
    "propriedades históricas do produto",
)
path.write_text(text, encoding="utf-8")


# Serializer do produto
path = Path("backend/inventory/serializers/catalog.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    package_description = serializers.CharField(read_only=True)\n\n    class Meta:",
    "    package_description = serializers.CharField(read_only=True)\n"
    "    deleted_by_name = serializers.CharField(\n"
    "        source=\"deleted_by.username\", read_only=True, allow_null=True\n"
    "    )\n"
    "    is_deleted = serializers.BooleanField(read_only=True)\n"
    "    display_status = serializers.CharField(read_only=True)\n\n"
    "    class Meta:",
    "campos históricos no serializer",
)
text = replace_once(
    text,
    "        read_only_fields = [\"stock\", \"created_at\", \"updated_at\"]",
    "        read_only_fields = [\n"
    "            \"stock\",\n"
    "            \"deleted_at\",\n"
    "            \"deleted_by\",\n"
    "            \"deletion_reason\",\n"
    "            \"created_at\",\n"
    "            \"updated_at\",\n"
    "        ]",
    "campos somente leitura do produto",
)
text = replace_once(
    text,
    "    def update(self, instance, validated_data):\n        if not validated_data.get(\"code\"):",
    "    def update(self, instance, validated_data):\n"
    "        if instance.is_deleted:\n"
    "            raise serializers.ValidationError(\n"
    "                \"Um produto excluído é mantido apenas para histórico e não pode ser alterado.\"\n"
    "            )\n"
    "        if not validated_data.get(\"code\"):",
    "bloqueio de edição de produto excluído",
)
path.write_text(text, encoding="utf-8")


# API de produtos
path = Path("backend/inventory/views/catalog.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    def after_activation_change(self, instance, active):\n        refresh_alerts(notify=True)\n\n    @staticmethod",
    "    def after_activation_change(self, instance, active):\n"
    "        refresh_alerts(notify=True)\n\n"
    "    def _set_activation(self, request, active):\n"
    "        product = self.get_object()\n"
    "        if product.is_deleted:\n"
    "            return Response(\n"
    "                {\n"
    "                    \"detail\": (\n"
    "                        \"Este produto foi excluído e permanece disponível somente para histórico. \"\n"
    "                        \"Não é possível ativá-lo, inativá-lo ou editá-lo.\"\n"
    "                    )\n"
    "                },\n"
    "                status=status.HTTP_400_BAD_REQUEST,\n"
    "            )\n"
    "        return super()._set_activation(request, active)\n\n"
    "    @staticmethod",
    "bloqueio de ativação de produto excluído",
)
start = "    def destroy(self, request, *args, **kwargs):\n"
end = "    def get_queryset(self):\n"
new_destroy = """    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        if product.is_deleted:
            return Response(self.get_serializer(product).data)

        blockers = self._deletion_blockers(product)
        if blockers:
            return Response(
                {
                    "detail": (
                        "Este produto ainda possui estoque ou vínculos operacionais e não pode ser excluído. "
                        "Exclua ou regularize os registros relacionados antes de continuar."
                    ),
                    "blockers": blockers,
                    "can_deactivate": product.active,
                },
                status=status.HTTP_409_CONFLICT,
            )

        metadata = {"product_id": product.pk, "code": product.code, "name": product.name}
        with transaction.atomic():
            product.active = False
            product.deleted_at = timezone.now()
            product.deleted_by = request.user
            product.deletion_reason = str(request.data.get("reason") or "").strip()
            product.save(
                update_fields=[
                    "active",
                    "deleted_at",
                    "deleted_by",
                    "deletion_reason",
                    "updated_at",
                ]
            )
            audit(
                request.user,
                "DELETE",
                product,
                "Produto excluído do uso operacional e mantido no histórico.",
                metadata=metadata,
            )

        refresh_alerts(notify=True)
        return Response(self.get_serializer(product).data)

"""
text = replace_section(text, start, end, new_destroy, "exclusão lógica na API")
text = replace_once(
    text,
    "        level = self.request.query_params.get(\"stock_level\")\n",
    "        deleted = str(self.request.query_params.get(\"deleted\") or \"\").lower()\n"
    "        if deleted == \"true\":\n"
    "            qs = qs.filter(deleted_at__isnull=False)\n"
    "        elif deleted != \"all\":\n"
    "            qs = qs.filter(deleted_at__isnull=True)\n\n"
    "        level = self.request.query_params.get(\"stock_level\")\n",
    "filtro de produtos excluídos",
)
text = replace_once(
    text,
    "        qs = self.filter_queryset(self.get_queryset().filter(stock__lte=F(\"minimum_stock\")))",
    "        qs = self.filter_queryset(\n"
    "            self.get_queryset().filter(\n"
    "                active=True, deleted_at__isnull=True, stock__lte=F(\"minimum_stock\")\n"
    "            )\n"
    "        )",
    "estoque baixo sem produtos excluídos",
)
text = replace_once(
    text,
    "        product = self.get_queryset().filter(barcode=value).first()",
    "        product = self.get_queryset().filter(\n"
    "            barcode=value, active=True, deleted_at__isnull=True\n"
    "        ).first()",
    "código de barras sem produtos excluídos",
)
path.write_text(text, encoding="utf-8")


# Migração
migration = '''from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_document_soft_delete_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="deleted_products",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="deletion_reason",
            field=models.TextField(blank=True),
        ),
    ]
'''
Path("backend/inventory/migrations/0007_product_soft_delete_history.py").write_text(
    migration, encoding="utf-8"
)


# Testes de governança
path = Path("backend/inventory/test_data_governance.py")
text = path.read_text(encoding="utf-8")
insert_before = "    def test_governance_records_cannot_be_deleted(self):\n"
new_tests = '''    def test_product_without_blockers_is_soft_deleted_and_kept_in_history(self):
        product = self.create_product()

        response = self.client.delete(
            f"/api/products/{product.id}/",
            {"reason": "Cadastro duplicado"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertTrue(product.is_deleted)
        self.assertFalse(product.active)
        self.assertEqual(product.deleted_by, self.admin)
        self.assertEqual(product.deletion_reason, "Cadastro duplicado")
        self.assertEqual(response.data["display_status"], "Excluído")

        deleted_list = self.client.get("/api/products/", {"deleted": "true"})
        self.assertEqual(deleted_list.status_code, 200, deleted_list.data)
        rows = deleted_list.data["results"] if isinstance(deleted_list.data, dict) else deleted_list.data
        self.assertIn(product.id, [row["id"] for row in rows])

    def test_deleted_product_cannot_be_reactivated_or_edited(self):
        product = self.create_product()
        delete_response = self.client.delete(f"/api/products/{product.id}/")
        self.assertEqual(delete_response.status_code, 200, delete_response.data)

        activate = self.client.post(f"/api/products/{product.id}/activate/")
        self.assertEqual(activate.status_code, 400, activate.data)

        update = self.client.patch(
            f"/api/products/{product.id}/",
            {"name": "Nome alterado"},
            format="json",
        )
        self.assertEqual(update.status_code, 400, update.data)
        product.refresh_from_db()
        self.assertEqual(product.name, "Produto de governança")

'''
text = replace_once(text, insert_before, new_tests + insert_before, "testes de produto excluído")
path.write_text(text, encoding="utf-8")


# Tela de produtos
path = Path("frontend/src/pages/products.jsx")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '  const list = useList("products/");',
    '  const list = useList("products/", { deleted: "all" });',
    "listagem histórica de produtos",
)
text = replace_once(
    text,
    "  function editProduct(row) {\n    setForm({",
    "  function editProduct(row) {\n    if (row.is_deleted) return;\n    setForm({",
    "bloqueio visual de edição",
)
text = replace_once(
    text,
    '        await api.delete(`products/${row.id}/`);\n        notify("Produto excluído permanentemente.");',
    '        await api.delete(`products/${row.id}/`, {\n          data: { reason: "Exclusão solicitada pelo usuário" },\n        });\n        notify("Produto excluído do uso operacional e mantido no histórico.");',
    "mensagem de exclusão lógica",
)
text = replace_once(
    text,
    'message: data.detail || "Este produto possui histórico e não pode ser excluído permanentemente.",',
    'message: data.detail || "Este produto ainda possui vínculos operacionais e não pode ser excluído.",',
    "mensagem de bloqueio",
)
old_delete_confirmation = '''    if (type === "delete") {
      return {
        title: "Excluir produto permanentemente",
        message: `Deseja realmente excluir “${row.name}”?`,
        detail: "Esta ação é irreversível. A exclusão só será permitida quando o produto estiver sem estoque e sem vínculos com lotes, entradas, saídas, ajustes, inventários ou movimentações.",
        confirmLabel: "Excluir permanentemente",
        confirmVariant: "danger",
      };
    }
'''
new_delete_confirmation = '''    if (type === "delete") {
      return {
        title: "Excluir produto",
        message: `Deseja excluir “${row.name}”?`,
        detail: "O produto deixará de ser utilizado em novas operações, mas continuará visível em cinza como Excluído para preservar o histórico. A exclusão só será permitida quando não houver estoque nem vínculos operacionais pendentes.",
        confirmLabel: "Excluir produto",
        confirmVariant: "danger",
      };
    }
'''
text = replace_once(text, old_delete_confirmation, new_delete_confirmation, "confirmação de exclusão")
text = replace_once(
    text,
    "  })();\n\n  return (",
    '''  })();

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

  return (''',
    "controle de filtro por situação",
)
old_status_select = '''        <select
          value={list.params.active ?? ""}
          onChange={(event) => list.setParams({ ...list.params, active: event.target.value, page: 1 })}
        >
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
'''
new_status_select = '''        <select
          value={productStatusFilter}
          onChange={(event) => changeProductStatus(event.target.value)}
        >
          <option value="">Todos os cadastros</option>
          <option value="ACTIVE">Somente ativos</option>
          <option value="INACTIVE">Somente inativos</option>
          <option value="DELETED">Somente excluídos</option>
        </select>
'''
text = replace_once(text, old_status_select, new_status_select, "filtro visual de excluídos")
text = replace_once(
    text,
    "          loading={list.loading}\n          rows={list.rows}\n          columns={[",
    "          loading={list.loading}\n"
    "          rows={list.rows}\n"
    "          rowClassName={(row) => row.is_deleted ? \"row-soft-deleted\" : (!row.active ? \"inactive-row\" : \"\")}\n"
    "          columns={[",
    "linha cinza para produto excluído",
)
text = replace_once(
    text,
    "                    <strong>{row.name}</strong>\n                    <small>{productSubtitle(row)}</small>",
    "                    <strong>{row.name}</strong>\n"
    "                    <small>{productSubtitle(row)}</small>\n"
    "                    {row.is_deleted && <small className=\"muted-text\">Mantido somente para histórico</small>}",
    "identificação histórica do produto",
)
old_status_column = '''              render: (row) => (
                <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} />
              ),
'''
new_status_column = '''              render: (row) => row.is_deleted
                ? <StatusBadge value="DELETED" label="Excluído" />
                : <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} />,
'''
text = replace_once(text, old_status_column, new_status_column, "status excluído")
text = replace_once(
    text,
    "                const [value, label] = stockLevel(row);\n                return <StatusBadge value={value} label={label} />;",
    "                if (row.is_deleted) return <StatusBadge value=\"DELETED\" label=\"Histórico\" />;\n"
    "                const [value, label] = stockLevel(row);\n"
    "                return <StatusBadge value={value} label={label} />;",
    "nível de estoque histórico",
)
action_start = '''            {
              key: "actions",
              label: "Ações",
'''
action_end = "          ]}"
new_actions = '''            {
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
'''
text = replace_section(text, action_start, action_end, new_actions, "ações do produto excluído")
path.write_text(text, encoding="utf-8")


# Produtos excluídos não aparecem em novos documentos
path = Path("frontend/src/pages/documents.jsx")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '      api.get("products/?page_size=500"),',
    '      api.get("products/?page_size=500&deleted=false"),',
    "produtos operacionais nos documentos",
)
path.write_text(text, encoding="utf-8")

print("Alterações de exclusão lógica de produtos aplicadas com sucesso.")
