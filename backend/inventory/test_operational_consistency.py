
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Category, InventoryCount, Lot, Product, StockAdjustment, UserProfile


User = get_user_model()


class OperationalConsistencyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "operational-admin",
            password="OperationalAdmin123!",
            is_staff=True,
            is_superuser=True,
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador operacional",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Refrigerantes operacionais")
        self.active_product = Product.objects.create(
            code="OP-ACTIVE",
            name="Produto ativo",
            category=self.category,
            stock=Decimal("10"),
            cost_price=Decimal("5"),
        )
        self.inactive_product = Product.objects.create(
            code="OP-INACTIVE",
            name="Produto inativo existente",
            category=self.category,
            stock=Decimal("4"),
            cost_price=Decimal("3"),
            active=False,
        )
        self.deleted_product = Product.objects.create(
            code="OP-DELETED",
            name="Produto excluído histórico",
            category=self.category,
            stock=Decimal("0"),
            active=False,
            deleted_at=timezone.now(),
            deleted_by=self.admin,
        )
        self.active_lot = Lot.objects.create(
            product=self.active_product,
            number="LOT-ACTIVE",
            received_quantity=Decimal("10"),
            quantity=Decimal("10"),
        )
        self.empty_lot = Lot.objects.create(
            product=self.inactive_product,
            number="LOT-EMPTY",
            received_quantity=Decimal("4"),
            quantity=Decimal("0"),
        )
        self.deleted_lot = Lot.objects.create(
            product=self.deleted_product,
            number="LOT-DELETED",
            received_quantity=Decimal("1"),
            quantity=Decimal("0"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @staticmethod
    def rows(response):
        return response.data.get("results", response.data)

    def test_lot_screen_hides_deleted_products_and_defaults_can_show_balance_only(self):
        response = self.client.get("/api/lots/", {"view": "available", "page_size": 100})
        self.assertEqual(response.status_code, 200, response.data)
        numbers = {row["number"] for row in self.rows(response)}
        self.assertEqual(numbers, {"LOT-ACTIVE"})

        all_existing = self.client.get("/api/lots/", {"view": "all", "page_size": 100})
        self.assertEqual(all_existing.status_code, 200, all_existing.data)
        numbers = {row["number"] for row in self.rows(all_existing)}
        self.assertEqual(numbers, {"LOT-ACTIVE", "LOT-EMPTY"})
        self.assertNotIn("LOT-DELETED", numbers)

    def test_inventory_includes_active_and_inactive_existing_products(self):
        response = self.client.post(
            "/api/inventories/",
            {"category": self.category.id, "notes": "Conferência", "populate": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], InventoryCount.OPEN)
        ids = {item["product"] for item in response.data["items"]}
        self.assertEqual(ids, {self.active_product.id, self.inactive_product.id})
        self.assertNotIn(self.deleted_product.id, ids)

    def test_adjustment_draft_confirmation_summary_and_cancellation(self):
        create = self.client.post(
            "/api/adjustments/",
            {
                "product": self.inactive_product.id,
                "type": StockAdjustment.POSITIVE,
                "quantity": 2,
                "reason": "Correção de contagem",
                "justification": "Duas unidades foram localizadas na conferência física.",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        self.assertEqual(create.data["status"], StockAdjustment.DRAFT)

        confirm = self.client.post(f"/api/adjustments/{create.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.assertEqual(confirm.data["status"], StockAdjustment.CONFIRMED)
        self.assertEqual(Decimal(str(confirm.data["movement_previous_stock"])), Decimal("4"))
        self.assertEqual(Decimal(str(confirm.data["movement_final_stock"])), Decimal("6"))

        summary = self.client.get("/api/adjustments/summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["confirmed"], 1)
        self.assertEqual(Decimal(str(summary.data["positive_quantity"])), Decimal("2"))

        cancel = self.client.post(f"/api/adjustments/{create.data['id']}/cancel/")
        self.assertEqual(cancel.status_code, 200, cancel.data)
        self.assertEqual(cancel.data["status"], StockAdjustment.CANCELLED)
        self.assertTrue(cancel.data["movement_reversed"])
        self.inactive_product.refresh_from_db()
        self.assertEqual(self.inactive_product.stock, Decimal("4"))

    def test_deleted_product_cannot_receive_adjustment(self):
        response = self.client.post(
            "/api/adjustments/",
            {
                "product": self.deleted_product.id,
                "type": StockAdjustment.POSITIVE,
                "quantity": 1,
                "reason": "Correção",
                "justification": "Não deve ser permitido.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("product", response.data)
