from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Alert,
    Category,
    InventoryCount,
    InventoryItem,
    Lot,
    Movement,
    Product,
    StockAdjustment,
    StockEntry,
    StockEntryItem,
    StockOutput,
    StockOutputItem,
    Supplier,
    UserProfile,
)
from .services import refresh_alerts

User = get_user_model()


class InventoryBaseTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="Admin123!", is_superuser=True, is_staff=True)
        UserProfile.objects.create(user=self.admin, full_name="Administrador", role=UserProfile.ADMIN)
        self.operator = User.objects.create_user("operador", password="Operador123!")
        UserProfile.objects.create(user=self.operator, full_name="Operador", role=UserProfile.OPERATOR)
        self.category = Category.objects.create(name="Cervejas")
        self.supplier = Supplier.objects.create(name="Fornecedor", document="00000000000191")
        self.product = Product.objects.create(
            code="P001",
            sku="SKU001",
            barcode="789000000001",
            name="Cerveja Pilsen",
            category=self.category,
            supplier=self.supplier,
            cost_price=Decimal("3.00"),
            sale_price=Decimal("4.50"),
            minimum_stock=Decimal("5"),
        )
        self.client = APIClient()


class LoginAndPermissionsTests(InventoryBaseTest):
    def test_login_returns_jwt(self):
        response = self.client.post("/api/auth/login/", {"username": "admin", "password": "Admin123!"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_operator_cannot_manage_users(self):
        self.client.force_authenticate(self.operator)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 403)

    def test_me_returns_role(self):
        self.client.force_authenticate(self.operator)
        response = self.client.get("/api/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"]["role"], "OPERATOR")


class ProductTests(InventoryBaseTest):
    def test_product_creation_and_uniqueness(self):
        self.client.force_authenticate(self.admin)
        payload = {
            "code": "P002",
            "sku": "SKU002",
            "barcode": "789000000002",
            "name": "Cerveja Lager",
            "category": self.category.pk,
            "supplier": self.supplier.pk,
            "cost_price": "4.00",
            "sale_price": "6.00",
            "minimum_stock": "2",
            "maximum_stock": "50",
            "package_quantity": "1",
        }
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        duplicate = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(duplicate.status_code, 400)


class EntryOutputRulesTests(InventoryBaseTest):
    def make_entry(self, quantity=Decimal("10"), lot="L1", expiration=None):
        entry = StockEntry.objects.create(supplier=self.supplier, user=self.admin)
        StockEntryItem.objects.create(entry=entry, product=self.product, quantity=quantity, unit_cost=Decimal("3.50"), lot_number=lot, expiration_date=expiration)
        return entry

    def test_entry_confirmation_increases_stock_and_lot(self):
        entry = self.make_entry()
        entry.confirm(self.admin)
        self.product.refresh_from_db()
        lot = Lot.objects.get(product=self.product, number="L1")
        self.assertEqual(self.product.stock, Decimal("10"))
        self.assertEqual(lot.quantity, Decimal("10"))
        self.assertEqual(Movement.objects.filter(type=Movement.ENTRY).count(), 1)
        with self.assertRaises(ValidationError):
            entry.confirm(self.admin)

    def test_output_blocks_negative_stock(self):
        output = StockOutput.objects.create(user=self.operator, reason="COMMERCIAL")
        StockOutputItem.objects.create(output=output, product=self.product, quantity=Decimal("1"))
        with self.assertRaises(ValidationError):
            output.confirm(self.operator)

    def test_fefo_and_output_cancellation(self):
        early = self.make_entry(Decimal("4"), "EARLY", timezone.localdate() + timedelta(days=10))
        late = self.make_entry(Decimal("6"), "LATE", timezone.localdate() + timedelta(days=30))
        early.confirm(self.admin)
        late.confirm(self.admin)
        output = StockOutput.objects.create(user=self.operator, reason="COMMERCIAL")
        StockOutputItem.objects.create(output=output, product=self.product, quantity=Decimal("5"))
        output.confirm(self.operator)
        self.assertEqual(Lot.objects.get(number="EARLY").quantity, Decimal("0"))
        self.assertEqual(Lot.objects.get(number="LATE").quantity, Decimal("5"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("5"))
        output.cancel(self.admin)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("10"))
        self.assertEqual(Movement.objects.filter(type=Movement.REVERSAL_IN).count(), 2)


class AdjustmentInventoryAlertTests(InventoryBaseTest):
    def test_adjustment_positive_and_negative(self):
        positive = StockAdjustment.objects.create(product=self.product, type=StockAdjustment.POSITIVE, quantity=Decimal("8"), reason="Correção", justification="Contagem física", user=self.admin)
        positive.confirm(self.admin)
        negative = StockAdjustment.objects.create(product=self.product, type=StockAdjustment.NEGATIVE, quantity=Decimal("3"), reason="Avaria", justification="Garrafas quebradas", user=self.admin)
        negative.confirm(self.admin)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("5"))

    def test_inventory_divergence_adjusts_stock(self):
        Movement.register(product=self.product, type=Movement.ADJUSTMENT_IN, quantity=10, user=self.admin, reason="Carga inicial")
        inventory = InventoryCount.objects.create(user=self.operator)
        InventoryItem.objects.create(inventory=inventory, product=self.product, system_quantity=10, counted_quantity=7, justification="Falta física")
        inventory.conclude(self.admin)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("7"))
        self.assertEqual(inventory.status, InventoryCount.DONE)

    def test_low_stock_and_expiry_alerts(self):
        self.product.stock = Decimal("2")
        self.product.save(update_fields=["stock"])
        Lot.objects.create(product=self.product, number="EXP", received_quantity=2, quantity=2, expiration_date=timezone.localdate() + timedelta(days=5), supplier=self.supplier)
        refresh_alerts(notify=False)
        self.assertTrue(Alert.objects.filter(type=Alert.LOW_STOCK, active=True).exists())
        self.assertTrue(Alert.objects.filter(type=Alert.EXPIRING, active=True).exists())


class ReportsTests(InventoryBaseTest):
    def setUp(self):
        super().setUp()
        Movement.register(product=self.product, type=Movement.ADJUSTMENT_IN, quantity=10, user=self.admin, reason="Carga")
        self.client.force_authenticate(self.admin)

    def test_report_preview_pdf_and_csv(self):
        today = timezone.localdate().isoformat()
        preview = self.client.get("/api/reports/preview/", {"type": "daily_movements", "date": today})
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["summary"]["total_movements"], 1)
        pdf = self.client.get("/api/reports/export.pdf", {"type": "daily_movements", "date": today})
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        csv = self.client.get("/api/reports/export.csv", {"type": "current_stock"})
        self.assertEqual(csv.status_code, 200)
        self.assertIn("text/csv", csv["Content-Type"])
