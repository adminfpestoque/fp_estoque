from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Category,
    Product,
    ProductPackaging,
    StockOutput,
    UserProfile,
)

User = get_user_model()


class OutputCheckoutTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "checkout-admin",
            password="CheckoutAdmin123!",
            email="checkout@example.com",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador do caixa",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Cervejas")
        self.product = Product.objects.create(
            code="CERV-001",
            name="Cerveja lata",
            category=self.category,
            stock=Decimal("24"),
            cost_price=Decimal("4.00"),
            sale_price=Decimal("6.00"),
        )
        self.box = ProductPackaging.objects.create(
            product=self.product,
            type=ProductPackaging.BOX,
            name="Caixa",
            units_per_package=12,
            cost_price=Decimal("48.00"),
            sale_price=Decimal("60.00"),
            is_default=True,
        )
        self.crate = ProductPackaging.objects.create(
            product=self.product,
            type=ProductPackaging.CRATE,
            name="Grade",
            units_per_package=24,
            cost_price=Decimal("96.00"),
            sale_price=Decimal("120.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def payload(self, *, packaging=None, sale_quantity=1, payment="CASH", received="100,00"):
        return {
            "output_date": timezone.now().isoformat(),
            "reason": "COMMERCIAL",
            "customer_name": "Cliente balcão",
            "payment_method": payment,
            "amount_received": received,
            "payment_reference": "",
            "notes": "Venda de teste",
            "items": [
                {
                    "product": self.product.id,
                    "packaging": packaging,
                    "sale_quantity": str(sale_quantity),
                    "lot": None,
                    "notes": "",
                }
            ],
        }

    def create_and_confirm(self, payload):
        create = self.client.post("/api/outputs/", payload, format="json")
        self.assertEqual(create.status_code, 201, create.data)
        confirm = self.client.post(f"/api/outputs/{create.data['id']}/confirm/")
        return create, confirm

    def test_product_api_persists_product_specific_packaging_options(self):
        response = self.client.patch(
            f"/api/products/{self.product.id}/",
            {
                "packaging_options": [
                    {
                        "id": self.box.id,
                        "type": ProductPackaging.BOX,
                        "name": "Caixa",
                        "units_per_package": 12,
                        "cost_price": "48,00",
                        "sale_price": "60,00",
                        "is_default": True,
                        "active": True,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["packaging_options"]), 1)
        option = response.data["packaging_options"][0]
        self.assertEqual(option["name"], "Caixa")
        self.assertEqual(option["units_per_package"], 12)
        self.assertFalse(ProductPackaging.objects.filter(pk=self.crate.pk).exists())

    def test_unit_sale_removes_only_selected_units_and_calculates_change(self):
        create, confirm = self.create_and_confirm(
            self.payload(packaging=None, sale_quantity=6, received="100,00")
        )
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("18"))
        item = confirm.data["items"][0]
        self.assertEqual(item["sale_unit_name"], "Unidade")
        self.assertEqual(Decimal(item["sale_quantity"]), Decimal("6"))
        self.assertEqual(Decimal(item["quantity"]), Decimal("6"))
        self.assertEqual(Decimal(confirm.data["total_value"]), Decimal("36.00"))
        self.assertEqual(Decimal(confirm.data["change_amount"]), Decimal("64.00"))
        self.assertEqual(create.data["status"], StockOutput.DRAFT)

    def test_box_sale_converts_packages_to_individual_stock_units(self):
        _, confirm = self.create_and_confirm(
            self.payload(packaging=self.box.id, sale_quantity=1, received="100,00")
        )
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("12"))
        item = confirm.data["items"][0]
        self.assertEqual(item["sale_unit_name"], "Caixa")
        self.assertEqual(item["conversion_factor"], 12)
        self.assertEqual(Decimal(item["quantity"]), Decimal("12"))
        self.assertEqual(Decimal(item["sale_price"]), Decimal("60.00"))
        self.assertEqual(Decimal(item["subtotal"]), Decimal("60.00"))

    def test_cash_payment_requires_enough_received_value(self):
        create = self.client.post(
            "/api/outputs/",
            self.payload(packaging=self.box.id, sale_quantity=1, received="50,00"),
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        confirm = self.client.post(f"/api/outputs/{create.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 400)
        self.assertIn("insuficiente", str(confirm.data).lower())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("24"))

    def test_commercial_output_requires_payment_method(self):
        create = self.client.post(
            "/api/outputs/",
            self.payload(payment="NONE", received="0"),
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        confirm = self.client.post(f"/api/outputs/{create.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 400)
        self.assertIn("forma de pagamento", str(confirm.data).lower())

    def test_invalid_packaging_from_other_product_is_rejected(self):
        other = Product.objects.create(
            code="REF-002",
            name="Refrigerante",
            category=self.category,
            stock=12,
            sale_price="5.00",
        )
        other_box = ProductPackaging.objects.create(
            product=other,
            name="Fardo",
            type=ProductPackaging.BUNDLE,
            units_per_package=6,
            cost_price=Decimal("20.00"),
            sale_price=Decimal("30.00"),
        )
        response = self.client.post(
            "/api/outputs/",
            self.payload(packaging=other_box.id),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("não pertence", str(response.data).lower())

    def test_editing_confirmed_output_recalculates_stock_and_total(self):
        _, confirmed = self.create_and_confirm(
            self.payload(packaging=self.box.id, sale_quantity=1, received="100,00")
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        output_id = confirmed.data["id"]

        payload = self.payload(packaging=None, sale_quantity=6, received="50,00")
        response = self.client.put(f"/api/outputs/{output_id}/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("18"))
        self.assertEqual(Decimal(response.data["total_value"]), Decimal("36.00"))
        self.assertEqual(Decimal(response.data["change_amount"]), Decimal("14.00"))

    def test_soft_delete_restores_stock_and_keeps_output_history(self):
        _, confirmed = self.create_and_confirm(
            self.payload(packaging=self.box.id, sale_quantity=1, received="100,00")
        )
        output_id = confirmed.data["id"]
        delete = self.client.delete(
            f"/api/outputs/{output_id}/",
            {"reason": "Venda lançada em duplicidade"},
            format="json",
        )
        self.assertEqual(delete.status_code, 200, delete.data)
        self.assertTrue(delete.data["is_deleted"])
        self.assertEqual(delete.data["display_status"], "Excluída")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("24"))
        history = self.client.get("/api/outputs/?deleted=true")
        rows = history.data.get("results", history.data)
        self.assertTrue(any(row["id"] == output_id for row in rows))

    def test_noncommercial_output_does_not_require_payment(self):
        payload = self.payload(payment="NONE", received="0")
        payload["reason"] = "INTERNAL"
        _, confirm = self.create_and_confirm(payload)
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.assertEqual(confirm.data["payment_method"], "NONE")
        self.assertEqual(Decimal(confirm.data["amount_received"]), Decimal("0.00"))
