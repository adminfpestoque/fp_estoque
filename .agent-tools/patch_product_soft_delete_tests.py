from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado: {label}")
    return text.replace(old, new, 1)


# Permite que ações de detalhe encontrem um produto já excluído para retornar
# uma mensagem clara, mantendo as listagens operacionais sem esses produtos.
path = Path("backend/inventory/views/catalog.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        deleted = str(self.request.query_params.get("deleted") or "").lower()
        if deleted == "true":
            qs = qs.filter(deleted_at__isnull=False)
        elif deleted != "all":
            qs = qs.filter(deleted_at__isnull=True)

        level = self.request.query_params.get("stock_level")
''',
    '''        deleted = str(self.request.query_params.get("deleted") or "").lower()
        detail_actions = {
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "activate",
            "deactivate",
        }
        if deleted == "true":
            qs = qs.filter(deleted_at__isnull=False)
        elif deleted != "all" and getattr(self, "action", None) not in detail_actions:
            qs = qs.filter(deleted_at__isnull=True)

        level = self.request.query_params.get("stock_level")
''',
    "consulta de detalhe de produto excluído",
)
path.write_text(text, encoding="utf-8")


# Atualiza a expectativa do teste antigo de remoção física.
path = Path("backend/inventory/test_products.py")
text = path.read_text(encoding="utf-8")
old = '''    def test_delete_product_permanently_when_it_has_no_stock_or_history(self):
        product = Product.objects.create(
            code="REF-002",
            name="Pepsi 2L",
            category=self.category,
            cost_price=Decimal("7.00"),
            sale_price=Decimal("11.00"),
        )

        response = self.client.delete(f"/api/products/{product.id}/")

        self.assertEqual(response.status_code, 204, getattr(response, "data", None))
        self.assertFalse(Product.objects.filter(id=product.id).exists())
'''
new = '''    def test_delete_product_keeps_it_in_history_when_it_has_no_stock_or_links(self):
        product = Product.objects.create(
            code="REF-002",
            name="Pepsi 2L",
            category=self.category,
            cost_price=Decimal("7.00"),
            sale_price=Decimal("11.00"),
        )

        response = self.client.delete(f"/api/products/{product.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertTrue(Product.objects.filter(id=product.id).exists())
        self.assertTrue(product.is_deleted)
        self.assertFalse(product.active)
        self.assertEqual(response.data["display_status"], "Excluído")
'''
text = replace_once(text, old, new, "teste de exclusão física do produto")
path.write_text(text, encoding="utf-8")

print("Consulta e testes de exclusão lógica do produto ajustados.")
