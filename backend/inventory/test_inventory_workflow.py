from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, InventoryCount, Movement, Product, UserProfile

User = get_user_model()


class InventoryWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "inventory-admin",
            password="InventoryAdmin123!",
            is_staff=True,
            is_superuser=True,
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador do inventário",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Refrigerantes")
        self.product = Product.objects.create(
            code="REF-001",
            name="Refrigerante teste",
            category=self.category,
            stock=Decimal("10.000"),
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def create_inventory(self):
        response = self.client.post(
            "/api/inventories/",
            {"category": self.category.id, "notes": "Contagem mensal", "populate": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_inventory_starts_with_pending_items(self):
        inventory = self.create_inventory()

        self.assertEqual(inventory["status"], InventoryCount.OPEN)
        self.assertEqual(inventory["total_items"], 1)
        self.assertEqual(inventory["counted_items"], 0)
        self.assertEqual(inventory["pending_items"], 1)
        self.assertEqual(inventory["progress_percent"], 0)

    def test_inventory_cannot_be_submitted_with_pending_items(self):
        inventory = self.create_inventory()

        response = self.client.post(f"/api/inventories/{inventory['id']}/submit/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("sem contagem", str(response.data))

    def test_divergence_requires_justification(self):
        inventory = self.create_inventory()

        response = self.client.post(
            f"/api/inventories/{inventory['id']}/bulk_count/",
            {
                "items": [
                    {
                        "product": self.product.id,
                        "counted_quantity": "8.000",
                        "justification": "",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("justification", response.data)

    def test_complete_inventory_adjusts_stock_and_records_responsible_users(self):
        inventory = self.create_inventory()

        count_response = self.client.post(
            f"/api/inventories/{inventory['id']}/bulk_count/",
            {
                "items": [
                    {
                        "product": self.product.id,
                        "counted_quantity": "8.000",
                        "justification": "Duas unidades não localizadas",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(count_response.status_code, 200, count_response.data)
        self.assertEqual(count_response.data["progress_percent"], 100)
        self.assertEqual(count_response.data["divergences_count"], 1)

        submit_response = self.client.post(
            f"/api/inventories/{inventory['id']}/submit/"
        )
        self.assertEqual(submit_response.status_code, 200, submit_response.data)
        self.assertEqual(submit_response.data["status"], InventoryCount.WAITING)
        self.assertEqual(submit_response.data["submitted_by_name"], self.admin.username)

        conclude_response = self.client.post(
            f"/api/inventories/{inventory['id']}/conclude/"
        )
        self.assertEqual(conclude_response.status_code, 200, conclude_response.data)
        self.assertEqual(conclude_response.data["status"], InventoryCount.DONE)
        self.assertEqual(conclude_response.data["completed_by_name"], self.admin.username)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("8.000"))
        movement = Movement.objects.get(document=inventory["number"])
        self.assertEqual(movement.type, Movement.ADJUSTMENT_OUT)
        self.assertEqual(movement.quantity, Decimal("2.000"))

    def test_active_inventory_blocks_overlapping_inventory(self):
        self.create_inventory()

        response = self.client.post(
            "/api/inventories/",
            {"category": self.category.id, "notes": "Duplicado", "populate": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Já existe", str(response.data))
