from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Movement, Product, Supplier, UserProfile

User = get_user_model()


class IntegerQuantityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "integer-admin",
            password="IntegerAdmin123!",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Sucos")
        self.supplier = Supplier.objects.create(name="Fornecedor de sucos")
        self.product = Product.objects.create(
            code="INT-001",
            name="Suco",
            category=self.category,
            stock=Decimal("10"),
            cost_price=Decimal("4.00"),
            sale_price=Decimal("6.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_service_rejects_fractional_and_negative_quantity(self):
        with self.assertRaises(ValidationError):
            Movement.register(
                product=self.product,
                type=Movement.OUTPUT,
                quantity="1,5",
                user=self.admin,
            )
        with self.assertRaises(ValidationError):
            Movement.register(
                product=self.product,
                type=Movement.OUTPUT,
                quantity="-1",
                user=self.admin,
            )

    def test_entry_api_accepts_integer_and_comma_money(self):
        response = self.client.post(
            "/api/entries/",
            {
                "supplier": self.supplier.id,
                "items": [
                    {
                        "product": self.product.id,
                        "quantity": "2",
                        "unit_cost": "4,75",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["items"][0]["quantity"], 2)
        self.assertEqual(response.data["items"][0]["unit_cost"], "4.75")
        self.assertEqual(response.data["total_value"], "9.50")

    def test_adjustment_api_rejects_fractional_quantity(self):
        response = self.client.post(
            "/api/adjustments/",
            {
                "product": self.product.id,
                "type": "POSITIVE",
                "quantity": "2.5",
                "reason": "Correção",
                "justification": "Teste",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("quantity", response.data)
