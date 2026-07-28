from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import (
    Alert,
    Category,
    Lot,
    Notification,
    PackagingType,
    Product,
    ProductPackaging,
    StockEntry,
    StockEntryItem,
    StockOutput,
    StockOutputItem,
    Supplier,
)
from .serializers import NotificationSerializer, ProductPackagingSerializer
from .services import refresh_alerts


class SystemHardeningTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_hardening",
            password="senha-segura-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(
            name="Refrigerantes",
            active=True,
        )
        self.container = PackagingType.objects.create(
            name="Lata",
            kind=PackagingType.CONTAINER,
            active=True,
        )
        self.grouping = PackagingType.objects.create(
            name="Fardo",
            kind=PackagingType.GROUPING,
            active=True,
        )
        self.product = Product.objects.create(
            code="PROD-HARDENING",
            name="Produto de teste",
            category=self.category,
            packaging=self.container,
            volume=350,
            volume_unit="ML",
            sale_price=Decimal("5.00"),
            cost_price=Decimal("5.00"),
            stock=Decimal("10"),
            minimum_stock=Decimal("2"),
            active=True,
        )

    def _credit_output(self, *, due_date, total_price="5.00"):
        output = StockOutput.objects.create(
            user=self.user,
            reason="COMMERCIAL",
            customer_name="Cliente Teste",
            payment_method=StockOutput.PAYMENT_ON_ACCOUNT,
            payment_due_date=due_date,
        )
        StockOutputItem.objects.create(
            output=output,
            product=self.product,
            sale_quantity=1,
            quantity=1,
            unit_sale_price=Decimal(total_price),
            sale_price=Decimal(total_price),
        )
        output.recalculate_total()
        output.refresh_from_db()
        return output

    def test_refresh_alerts_is_idempotent_for_alerts_and_notifications(self):
        self.product.stock = 0
        self.product.save(update_fields=["stock", "updated_at"])

        refresh_alerts(notify=True)
        refresh_alerts(notify=True)

        alert = Alert.objects.get(
            active=True,
            type=Alert.OUT_OF_STOCK,
            product=self.product,
        )
        self.assertEqual(
            Alert.objects.filter(
                active=True,
                type=Alert.OUT_OF_STOCK,
                product=self.product,
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(user=self.user, alert=alert).count(),
            1,
        )

    def test_overdue_credit_creates_linked_notification_reference(self):
        output = self._credit_output(
            due_date=timezone.localdate() - timedelta(days=1),
        )

        refresh_alerts(notify=True)

        alert = Alert.objects.get(
            active=True,
            type=Alert.CREDIT_OVERDUE,
            output=output,
        )
        notification = Notification.objects.get(user=self.user, alert=alert)
        serialized = NotificationSerializer(notification).data

        self.assertEqual(serialized["output_number"], output.number)
        self.assertEqual(serialized["customer_name"], "Cliente Teste")
        self.assertIn(output.number, serialized["reference_display"])
        self.assertFalse(notification.read)

    def test_credit_stays_pending_without_received_value_until_confirmation(self):
        output = self._credit_output(
            due_date=timezone.localdate() + timedelta(days=5),
        )

        self.assertEqual(output.status, StockOutput.DRAFT)
        self.assertEqual(output.payment_status, "PENDING")
        self.assertEqual(output.amount_received, Decimal("0.00"))

        output.confirm(self.user, require_payment=True)
        output.refresh_from_db()

        self.assertEqual(output.status, StockOutput.CONFIRMED)
        self.assertEqual(output.payment_status, "PAID")
        self.assertEqual(output.amount_received, output.total_value)

    def test_cancelling_entry_restores_weighted_cost_and_lot_received_quantity(self):
        supplier = Supplier.objects.create(name="Fornecedor Teste", active=True)
        entry = StockEntry.objects.create(
            supplier=supplier,
            user=self.user,
        )
        StockEntryItem.objects.create(
            entry=entry,
            product=self.product,
            entry_quantity=10,
            quantity=10,
            purchase_price=Decimal("10.00"),
            unit_cost=Decimal("10.00"),
            lot_number="LOTE-ENTRADA",
        )

        entry.confirm(self.user)
        self.product.refresh_from_db()
        lot = Lot.objects.get(product=self.product, number="LOTE-ENTRADA")

        self.assertEqual(self.product.stock, Decimal("20.000"))
        self.assertEqual(self.product.cost_price, Decimal("7.50"))
        self.assertEqual(lot.received_quantity, Decimal("10.000"))
        self.assertEqual(lot.quantity, Decimal("10.000"))

        entry.cancel(self.user)
        self.product.refresh_from_db()
        lot.refresh_from_db()

        self.assertEqual(self.product.stock, Decimal("10.000"))
        self.assertEqual(self.product.cost_price, Decimal("5.00"))
        self.assertEqual(lot.received_quantity, Decimal("0.000"))
        self.assertEqual(lot.quantity, Decimal("0.000"))
        self.assertFalse(lot.active)

    def test_active_alert_notification_cannot_be_deleted_or_cleared(self):
        self.product.stock = 0
        self.product.save(update_fields=["stock", "updated_at"])
        refresh_alerts(notify=True)

        notification = Notification.objects.get(
            user=self.user,
            alert__type=Alert.OUT_OF_STOCK,
            alert__active=True,
        )
        notification.read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["read", "read_at", "updated_at"])

        delete_response = self.client.delete(
            f"/api/notifications/{notification.pk}/"
        )
        self.assertEqual(delete_response.status_code, 409)

        clear_response = self.client.delete("/api/notifications/clear_read/")
        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(clear_response.data["deleted"], 0)
        self.assertEqual(clear_response.data["preserved_active"], 1)
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())

    def test_existing_packaging_cannot_switch_to_inactive_grouping(self):
        option = ProductPackaging.objects.create(
            product=self.product,
            packaging_type=self.grouping,
            units_per_package=6,
            sale_price=Decimal("25.00"),
            active=True,
            is_default=True,
        )
        inactive = PackagingType.objects.create(
            name="Caixa inativa",
            kind=PackagingType.GROUPING,
            active=False,
        )

        serializer = ProductPackagingSerializer(
            option,
            data={"packaging_type": inactive.pk},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("packaging_type", serializer.errors)
