from pathlib import Path

path = Path("backend/inventory/test_document_history.py")
text = path.read_text(encoding="utf-8")
start_marker = "    def test_product_can_be_permanently_deleted_after_documents_are_soft_deleted(self):\n"
end_marker = "    def test_product_remains_blocked_while_document_is_not_deleted(self):\n"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("Não foi possível localizar o teste antigo de exclusão permanente do produto.")

replacement = '''    def test_product_is_soft_deleted_after_documents_are_soft_deleted(self):
        entry = self.create_confirmed_entry(quantity=5)
        output = self.create_confirmed_output(quantity=5)
        self.assertEqual(self.product.stock, Decimal("0"))

        output_delete = self.client.delete(f"/api/outputs/{output.id}/", format="json")
        self.assertEqual(output_delete.status_code, 200, output_delete.data)
        entry_delete = self.client.delete(f"/api/entries/{entry.id}/", format="json")
        self.assertEqual(entry_delete.status_code, 200, entry_delete.data)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("0"))

        product_delete = self.client.delete(
            f"/api/products/{self.product.id}/",
            {"reason": "Produto descontinuado"},
            format="json",
        )
        self.assertEqual(product_delete.status_code, 200, product_delete.data)

        self.product.refresh_from_db()
        self.assertTrue(Product.objects.filter(pk=self.product.id).exists())
        self.assertTrue(self.product.is_deleted)
        self.assertFalse(self.product.active)
        self.assertEqual(self.product.deletion_reason, "Produto descontinuado")
        self.assertEqual(product_delete.data["display_status"], "Excluído")

        entry.refresh_from_db()
        output.refresh_from_db()
        entry_item = entry.items.get()
        output_item = output.items.get()
        self.assertEqual(entry_item.product_id, self.product.id)
        self.assertEqual(output_item.product_id, self.product.id)
        self.assertEqual(entry_item.product_name_snapshot, "Produto histórico")
        self.assertEqual(output_item.product_name_snapshot, "Produto histórico")
        self.assertTrue(entry.is_deleted)
        self.assertTrue(output.is_deleted)
        self.assertTrue(Movement.objects.filter(product=self.product).exists())
        self.assertTrue(Lot.objects.filter(product=self.product).exists())

'''
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
print("Teste de histórico de produto ajustado.")
