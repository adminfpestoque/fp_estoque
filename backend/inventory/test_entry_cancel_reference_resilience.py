from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from .models import Category, Product, StockEntry, StockEntryItem, Supplier


class EntryCancelReferenceResilienceTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="entry-cancel-resilience-admin",
            password="EntryCancelResilience123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name="Bebidas cancelamento resiliente")
        self.supplier = Supplier.objects.create(name="Fornecedor cancelamento resiliente")

    def _confirmed_entry(self, code):
        product = Product.objects.create(
            code=code,
            name=f"Produto {code}",
            category=self.category,
            cost_price=Decimal("2.00"),
            sale_price=Decimal("4.00"),
        )
        entry = StockEntry.objects.create(
            supplier=self.supplier,
            user=self.user,
        )
        StockEntryItem.objects.create(
            entry=entry,
            product=product,
            entry_quantity=5,
            quantity=5,
            purchase_price=Decimal("10.00"),
            unit_cost=Decimal("2.00"),
        )
        entry.recalculate_total()
        entry.confirm(self.user)
        product.refresh_from_db()
        self.assertEqual(product.stock, Decimal("5"))
        return entry, product

    def test_cancel_keeps_stock_reversal_when_supplier_cost_reference_refresh_fails(self):
        entry, product = self._confirmed_entry("CANCEL-REF-001")

        with patch(
            "inventory.models.consistency.ProductSupplier.objects.select_for_update",
            side_effect=RuntimeError("falha simulada na referência de custo"),
        ):
            response = self.client.post(f"/api/entries/{entry.pk}/cancel/")

        self.assertEqual(response.status_code, 200, response.data)
        entry.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(entry.status, StockEntry.CANCELLED)
        self.assertEqual(product.stock, Decimal("0"))

    def test_delete_keeps_soft_delete_when_supplier_cost_reference_refresh_fails(self):
        entry, product = self._confirmed_entry("DELETE-REF-001")

        with patch(
            "inventory.models.consistency.ProductSupplier.objects.select_for_update",
            side_effect=RuntimeError("falha simulada na referência de custo"),
        ):
            response = self.client.delete(
                f"/api/entries/{entry.pk}/",
                {"reason": "Exclusão de teste"},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        entry.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(entry.status, StockEntry.CANCELLED)
        self.assertTrue(entry.is_deleted)
        self.assertEqual(product.stock, Decimal("0"))
