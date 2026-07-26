from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Category,
    PackagingType,
    Product,
    ProductPackaging,
    StockEntry,
    Supplier,
    UserProfile,
)

User = get_user_model()


class UnifiedPackagingFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "packaging-admin",
            password="PackagingAdmin123!",
            email="packaging@example.com",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador de embalagens",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Gelo e bebidas")
        self.supplier = Supplier.objects.create(name="Distribuidor teste")
        self.product = Product.objects.create(
            code="GELO-001",
            name="Gelo",
            category=self.category,
            supplier=self.supplier,
            stock=Decimal("0"),
            cost_price=Decimal("2.50"),
            sale_price=Decimal("5.00"),
        )
        self.package_type = PackagingType.objects.create(name="Pacote")
        self.package = ProductPackaging.objects.create(
            product=self.product,
            packaging_type=self.package_type,
            units_per_package=12,
            cost_price=Decimal("30.00"),
            sale_price=Decimal("5.00"),
            is_default=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_entry_by_package_adds_real_units_and_uses_package_purchase_price(self):
        response = self.client.post(
            "/api/entries/",
            {
                "supplier": self.supplier.id,
                "entry_date": timezone.now().isoformat(),
                "invoice_number": "",
                "notes": "",
                "items": [
                    {
                        "product": self.product.id,
                        "packaging": self.package.id,
                        "entry_quantity": 2,
                        "purchase_price": "30,00",
                        "lot_number": "GELO-LOTE-1",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        item = response.data["items"][0]
        self.assertEqual(item["entry_unit_name"], "Pacote")
        self.assertEqual(item["conversion_factor"], 12)
        self.assertEqual(Decimal(item["quantity"]), Decimal("24"))
        self.assertEqual(Decimal(item["unit_cost"]), Decimal("2.50"))
        self.assertEqual(Decimal(item["subtotal"]), Decimal("60.00"))
        self.assertEqual(Decimal(response.data["total_value"]), Decimal("60.00"))

        confirm = self.client.post(f"/api/entries/{response.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("24"))

    def test_output_package_price_is_not_multiplied_by_contained_units(self):
        self.product.stock = Decimal("24")
        self.product.save(update_fields=["stock", "updated_at"])
        create = self.client.post(
            "/api/outputs/",
            {
                "output_date": timezone.now().isoformat(),
                "reason": "COMMERCIAL",
                "payment_method": "CASH",
                "amount_received": "10,00",
                "items": [
                    {
                        "product": self.product.id,
                        "packaging": self.package.id,
                        "sale_quantity": 1,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        self.assertEqual(Decimal(create.data["total_value"]), Decimal("5.00"))
        item = create.data["items"][0]
        self.assertEqual(Decimal(item["quantity"]), Decimal("12"))
        self.assertEqual(Decimal(item["sale_price"]), Decimal("5.00"))
        self.assertEqual(Decimal(item["subtotal"]), Decimal("5.00"))

        confirm = self.client.post(f"/api/outputs/{create.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("12"))
        self.assertEqual(Decimal(confirm.data["change_amount"]), Decimal("5.00"))

    def test_packaging_type_catalog_is_used_only_by_products(self):
        box_type = self.client.post(
            "/api/packaging-types/",
            {"name": "Caixa térmica", "active": True},
            format="json",
        )
        self.assertEqual(box_type.status_code, 201, box_type.data)

        category = self.client.patch(
            f"/api/categories/{self.category.id}/",
            {"name": "Gelo e bebidas geladas", "description": "Categoria sem vínculo com embalagem."},
            format="json",
        )
        self.assertEqual(category.status_code, 200, category.data)
        self.assertNotIn("packaging_types", category.data)
        self.assertNotIn("packaging_type_names", category.data)

        product = self.client.patch(
            f"/api/products/{self.product.id}/",
            {
                "packaging_options": [
                    {
                        "packaging_type": box_type.data["id"],
                        "units_per_package": 24,
                        "cost_price": "55,00",
                        "sale_price": "9,00",
                        "is_default": True,
                        "active": True,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(product.status_code, 200, product.data)
        self.assertEqual(len(product.data["packaging_options"]), 1)
        self.assertEqual(product.data["packaging_options"][0]["packaging_type_name"], "Caixa térmica")

        types = self.client.get("/api/packaging-types/?page_size=500")
        self.assertEqual(types.status_code, 200)
        rows = types.data.get("results", types.data)
        self.assertTrue(any(row["name"] == "Caixa térmica" for row in rows))

    def test_packaging_type_in_use_cannot_be_deleted(self):
        response = self.client.delete(f"/api/packaging-types/{self.package_type.id}/")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertIn("inative", response.data["detail"].lower())

    def test_legacy_unit_entry_payload_remains_compatible(self):
        response = self.client.post(
            "/api/entries/",
            {
                "supplier": self.supplier.id,
                "entry_date": timezone.now().isoformat(),
                "items": [
                    {
                        "product": self.product.id,
                        "quantity": 3,
                        "unit_cost": "2,50",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        item = response.data["items"][0]
        self.assertEqual(item["entry_unit_name"], "Unidade")
        self.assertEqual(Decimal(item["quantity"]), Decimal("3"))
        self.assertEqual(Decimal(item["purchase_price"]), Decimal("2.50"))
        self.assertEqual(Decimal(response.data["total_value"]), Decimal("7.50"))
