from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from .models import Category, Product, StockEntry, StockEntryItem, Supplier


class DocumentDeleteResilienceTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="delete-resilience-admin",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name="Categoria exclusão resiliente")
        self.supplier = Supplier.objects.create(name="Fornecedor exclusão resiliente")
        self.product = Product.objects.create(
            code="DELETE-RESILIENCE",
            name="Produto exclusão resiliente",
            category=self.category,
            cost_price=Decimal("2.00"),
            sale_price=Decimal("4.00"),
        )

    def _confirmed_entry(self):
        entry = StockEntry.objects.create(
            supplier=self.supplier,
            user=self.user,
        )
        StockEntryItem.objects.create(
            entry=entry,
            product=self.product,
            entry_quantity=5,
            quantity=5,
            purchase_price=Decimal("10.00"),
            unit_cost=Decimal("10.00"),
            lot_number="LOT-DELETE-RESILIENCE",
        )
        entry.confirm(self.user)
        return entry

    def test_confirmed_entry_delete_returns_success_if_post_delete_serialization_fails(self):
        entry = self._confirmed_entry()

        with patch(
            "inventory.views.documents.StockEntryViewSet.get_serializer",
            side_effect=RuntimeError("falha simulada depois da exclusão"),
        ):
            response = self.client.delete(
                f"/api/entries/{entry.pk}/",
                {"reason": "Teste de exclusão resiliente"},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_deleted"])
        self.assertEqual(response.data["display_status"], "Excluída")

        entry.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(entry.is_deleted)
        self.assertEqual(entry.status, StockEntry.CANCELLED)
        self.assertEqual(self.product.stock, Decimal("0.000"))
