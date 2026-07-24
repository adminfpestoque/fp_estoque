from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Category,
    Lot,
    Movement,
    Product,
    StockEntry,
    StockEntryItem,
    StockOutput,
    StockOutputItem,
    Supplier,
    UserProfile,
)

User = get_user_model()


class DocumentHistoryTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin-history",
            password="AdminHistory123",
            email="admin-history@example.com",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Bebidas")
        self.supplier = Supplier.objects.create(name="Fornecedor teste")
        self.product = Product.objects.create(
            code="HIST-001",
            name="Produto histórico",
            category=self.category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("9.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def create_confirmed_entry(self, quantity=10):
        entry = StockEntry.objects.create(
            supplier=self.supplier,
            user=self.admin,
            invoice_number="NF-001",
        )
        StockEntryItem.objects.create(
            entry=entry,
            product=self.product,
            quantity=quantity,
            unit_cost=Decimal("5.00"),
            lot_number="LOTE-HIST",
        )
        entry.recalculate_total()
        entry.confirm(self.admin)
        self.product.refresh_from_db()
        return entry

    def create_confirmed_output(self, quantity=4):
        output = StockOutput.objects.create(
            user=self.admin,
            reason="COMMERCIAL",
        )
        StockOutputItem.objects.create(
            output=output,
            product=self.product,
            quantity=quantity,
        )
        output.confirm(self.admin)
        self.product.refresh_from_db()
        return output

    def entry_payload(self, entry, quantity):
        return {
            "supplier": self.supplier.id,
            "entry_date": timezone.localtime(entry.entry_date).isoformat(),
            "invoice_number": "NF-CORRIGIDA",
            "notes": "Entrada atualizada",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": str(quantity),
                    "unit_cost": "6,00",
                    "lot_number": "LOTE-HIST",
                    "manufacturing_date": None,
                    "expiration_date": None,
                    "notes": "",
                }
            ],
        }

    def output_payload(self, output, quantity):
        return {
            "output_date": timezone.localtime(output.output_date).isoformat(),
            "reason": "COMMERCIAL",
            "notes": "Saída atualizada",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": str(quantity),
                    "lot": None,
                    "notes": "",
                }
            ],
        }

    def test_confirmed_entry_can_be_updated_and_stock_is_recalculated(self):
        entry = self.create_confirmed_entry(quantity=10)
        self.assertEqual(self.product.stock, Decimal("10"))

        response = self.client.put(
            f"/api/entries/{entry.id}/",
            self.entry_payload(entry, quantity=6),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        entry.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(entry.status, StockEntry.CONFIRMED)
        self.assertEqual(entry.items.get().quantity, Decimal("6"))
        self.assertEqual(self.product.stock, Decimal("6"))

    def test_confirmed_output_can_be_updated_and_stock_is_recalculated(self):
        self.create_confirmed_entry(quantity=10)
        output = self.create_confirmed_output(quantity=4)
        self.assertEqual(self.product.stock, Decimal("6"))

        response = self.client.put(
            f"/api/outputs/{output.id}/",
            self.output_payload(output, quantity=2),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        output.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(output.status, StockOutput.CONFIRMED)
        self.assertEqual(output.items.get().quantity, Decimal("2"))
        self.assertEqual(self.product.stock, Decimal("8"))

    def test_deleting_confirmed_output_keeps_gray_history_and_restores_stock(self):
        self.create_confirmed_entry(quantity=10)
        output = self.create_confirmed_output(quantity=3)
        self.assertEqual(self.product.stock, Decimal("7"))

        response = self.client.delete(
            f"/api/outputs/{output.id}/",
            {"reason": "Registro duplicado"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        output.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(output.is_deleted)
        self.assertEqual(output.status, StockOutput.CANCELLED)
        self.assertEqual(output.deletion_reason, "Registro duplicado")
        self.assertEqual(self.product.stock, Decimal("10"))
        self.assertEqual(response.data["display_status"], "Excluída")

        list_response = self.client.get("/api/outputs/")
        self.assertEqual(list_response.status_code, 200)
        rows = list_response.data.get("results", list_response.data)
        deleted_row = next(row for row in rows if row["id"] == output.id)
        self.assertTrue(deleted_row["is_deleted"])

    def test_deleted_document_cannot_be_updated(self):
        entry = StockEntry.objects.create(supplier=self.supplier, user=self.admin)
        StockEntryItem.objects.create(
            entry=entry,
            product=self.product,
            quantity=1,
            unit_cost=Decimal("5.00"),
        )
        entry.recalculate_total()
        entry.soft_delete(self.admin)

        response = self.client.put(
            f"/api/entries/{entry.id}/",
            self.entry_payload(entry, quantity=2),
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_product_is_soft_deleted_after_documents_are_soft_deleted(self):
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

    def test_product_remains_blocked_while_document_is_not_deleted(self):
        entry = self.create_confirmed_entry(quantity=5)
        output = self.create_confirmed_output(quantity=5)
        self.assertEqual(self.product.stock, Decimal("0"))

        response = self.client.delete(f"/api/products/{self.product.id}/")

        self.assertEqual(response.status_code, 409)
        blocker_codes = {item["code"] for item in response.data["blockers"]}
        self.assertIn("entries", blocker_codes)
        self.assertIn("outputs", blocker_codes)
        self.assertTrue(StockEntry.objects.filter(pk=entry.pk).exists())
        self.assertTrue(StockOutput.objects.filter(pk=output.pk).exists())
