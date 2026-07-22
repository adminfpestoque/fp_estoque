from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Category,
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


class DashboardCommercialTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-dashboard",
            password="Admin123!",
            is_superuser=True,
            is_staff=True,
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador Dashboard",
            role=UserProfile.ADMIN,
        )
        self.category = Category.objects.create(name="Cervejas Dashboard")
        self.other_category = Category.objects.create(name="Refrigerantes Dashboard")
        self.supplier = Supplier.objects.create(name="Fornecedor Dashboard")
        self.product = Product.objects.create(
            code="DASH-001",
            name="Produto Dashboard",
            category=self.category,
            supplier=self.supplier,
            cost_price=Decimal("22.00"),
            sale_price=Decimal("186.00"),
            minimum_stock=Decimal("2"),
        )
        self.other_product = Product.objects.create(
            code="DASH-002",
            name="Produto Outra Categoria",
            category=self.other_category,
            supplier=self.supplier,
            cost_price=Decimal("10.00"),
            sale_price=Decimal("20.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def add_stock(self, product, quantity, unit_cost):
        entry = StockEntry.objects.create(supplier=self.supplier, user=self.admin)
        StockEntryItem.objects.create(
            entry=entry,
            product=product,
            quantity=quantity,
            unit_cost=unit_cost,
            lot_number=f"LOTE-{product.code}",
        )
        entry.confirm(self.admin)

    def create_output(self, product, quantity, reason):
        output = StockOutput.objects.create(user=self.admin, reason=reason)
        StockOutputItem.objects.create(output=output, product=product, quantity=quantity)
        output.confirm(self.admin)
        return output

    def test_dashboard_filters_sales_profit_and_current_stock(self):
        self.add_stock(self.product, Decimal("10"), Decimal("22.00"))
        self.create_output(self.product, Decimal("3"), "COMMERCIAL")
        self.create_output(self.product, Decimal("1"), "INTERNAL")

        movement = Movement.objects.filter(
            product=self.product,
            type=Movement.OUTPUT,
            output__reason="COMMERCIAL",
        ).first()
        self.assertEqual(movement.unit_sale_price, Decimal("186.00"))

        self.product.sale_price = Decimal("200.00")
        self.product.save(update_fields=["sale_price"])

        response = self.client.get(
            "/api/dashboard/",
            {"period": "today", "product": self.product.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(str(response.data["sales"]["quantity_sold"])), Decimal("3"))
        self.assertEqual(Decimal(str(response.data["sales"]["revenue"])), Decimal("558.00"))
        self.assertEqual(Decimal(str(response.data["sales"]["cost"])), Decimal("66.00"))
        self.assertEqual(Decimal(str(response.data["sales"]["gross_profit"])), Decimal("492.00"))
        self.assertEqual(Decimal(str(response.data["sales"]["current_stock"])), Decimal("6"))
        self.assertEqual(Decimal(str(response.data["sales"]["current_stock_sale"])), Decimal("1200.00"))
        self.assertEqual(response.data["sales"]["sales_documents"], 1)
        self.assertEqual(len(response.data["product_performance"]), 1)

    def test_dashboard_category_filter_excludes_other_categories(self):
        self.add_stock(self.product, Decimal("5"), Decimal("22.00"))
        self.add_stock(self.other_product, Decimal("8"), Decimal("10.00"))
        self.create_output(self.product, Decimal("2"), "COMMERCIAL")
        self.create_output(self.other_product, Decimal("4"), "COMMERCIAL")

        response = self.client.get(
            "/api/dashboard/",
            {"period": "today", "category": self.category.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(str(response.data["sales"]["quantity_sold"])), Decimal("2"))
        self.assertEqual(response.data["products"], 1)
        self.assertEqual(response.data["product_performance"][0]["name"], self.product.name)
