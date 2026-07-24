from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Lot, Product, Supplier, UserProfile

User = get_user_model()


class DataGovernanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "governance-admin",
            password="GovernanceAdmin123!",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador de governança",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Bebidas")
        self.supplier = Supplier.objects.create(name="Fornecedor principal")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def create_product(self, **overrides):
        values = {
            "code": "GOV-001",
            "name": "Produto de governança",
            "category": self.category,
            "supplier": self.supplier,
            "stock": Decimal("0"),
            "cost_price": Decimal("3.00"),
            "sale_price": Decimal("5.00"),
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_product_can_be_activated_and_deactivated_without_deletion(self):
        product = self.create_product()

        deactivate = self.client.post(f"/api/products/{product.id}/deactivate/")
        self.assertEqual(deactivate.status_code, 200, deactivate.data)
        product.refresh_from_db()
        self.assertFalse(product.active)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

        activate = self.client.post(f"/api/products/{product.id}/activate/")
        self.assertEqual(activate.status_code, 200, activate.data)
        product.refresh_from_db()
        self.assertTrue(product.active)

    def test_product_with_stock_cannot_be_permanently_deleted(self):
        product = self.create_product(stock=Decimal("4"))

        response = self.client.delete(f"/api/products/{product.id}/")

        self.assertEqual(response.status_code, 409, response.data)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertIn("stock", [item["code"] for item in response.data["blockers"]])
        self.assertTrue(response.data["can_deactivate"])

    def test_product_with_history_cannot_be_permanently_deleted(self):
        product = self.create_product()
        Lot.objects.create(product=product, number="LOTE-GOV")

        response = self.client.delete(f"/api/products/{product.id}/")

        self.assertEqual(response.status_code, 409, response.data)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertIn("lots", [item["code"] for item in response.data["blockers"]])

    def test_governance_records_cannot_be_deleted(self):
        category_response = self.client.delete(f"/api/categories/{self.category.id}/")
        supplier_response = self.client.delete(f"/api/suppliers/{self.supplier.id}/")

        self.assertEqual(category_response.status_code, 405, category_response.data)
        self.assertEqual(supplier_response.status_code, 405, supplier_response.data)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(Supplier.objects.filter(pk=self.supplier.pk).exists())

    def test_governance_records_can_be_activated_and_deactivated(self):
        for endpoint, instance in (
            ("categories", self.category),
            ("suppliers", self.supplier),
        ):
            deactivate = self.client.post(f"/api/{endpoint}/{instance.id}/deactivate/")
            self.assertEqual(deactivate.status_code, 200, deactivate.data)
            instance.refresh_from_db()
            self.assertFalse(instance.active)

            activate = self.client.post(f"/api/{endpoint}/{instance.id}/activate/")
            self.assertEqual(activate.status_code, 200, activate.data)
            instance.refresh_from_db()
            self.assertTrue(instance.active)

    def test_user_status_is_changed_without_deleting_account(self):
        operator = User.objects.create_user(
            "governance-operator",
            password="GovernanceOperator123!",
        )
        profile = UserProfile.objects.create(
            user=operator,
            full_name="Operador",
            role=UserProfile.OPERATOR,
        )

        deactivate = self.client.post(f"/api/users/{operator.id}/deactivate/")
        self.assertEqual(deactivate.status_code, 200, deactivate.data)
        operator.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(operator.is_active)
        self.assertFalse(profile.active)
        self.assertTrue(User.objects.filter(pk=operator.pk).exists())

        activate = self.client.post(f"/api/users/{operator.id}/activate/")
        self.assertEqual(activate.status_code, 200, activate.data)
        operator.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(operator.is_active)
        self.assertTrue(profile.active)

    def test_user_cannot_deactivate_current_account(self):
        response = self.client.post(f"/api/users/{self.admin.id}/deactivate/")

        self.assertEqual(response.status_code, 400, response.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
