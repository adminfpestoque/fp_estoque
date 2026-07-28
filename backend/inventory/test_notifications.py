from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Alert, Category, Notification, Product, UserProfile
from .services import refresh_alerts

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "notification-admin",
            password="NotificationAdmin123!",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )
        self.operator = User.objects.create_user(
            "notification-operator",
            password="NotificationOperator123!",
        )
        UserProfile.objects.create(
            user=self.operator,
            full_name="Operador",
            role=UserProfile.OPERATOR,
        )
        self.category = Category.objects.create(name="Águas")
        self.product = Product.objects.create(
            code="NOT-001",
            name="Água mineral",
            category=self.category,
            stock=Decimal("2"),
            minimum_stock=Decimal("5"),
            cost_price=Decimal("1.50"),
            sale_price=Decimal("2.50"),
        )
        self.client = APIClient()

    def test_refresh_is_idempotent_and_resolves_stale_alerts(self):
        first = refresh_alerts(notify=True)
        second = refresh_alerts(notify=True)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(Alert.objects.filter(active=True).count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

        alert = Alert.objects.get(active=True)
        operator_notice = Notification.objects.get(user=self.operator, alert=alert)
        operator_notice.read = True
        operator_notice.save(update_fields=["read"])

        self.product.stock = Decimal("1")
        self.product.save(update_fields=["stock"])
        refresh_alerts(notify=True)

        self.assertEqual(Alert.objects.filter(active=True).count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        operator_notice.refresh_from_db()
        self.assertFalse(operator_notice.read)
        self.assertIn("1 unidade", operator_notice.message)

        self.product.stock = Decimal("10")
        self.product.save(update_fields=["stock"])
        refresh_alerts(notify=True)

        alert.refresh_from_db()
        self.assertFalse(alert.active)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(Notification.objects.count(), 2)

    def test_notification_actions_are_user_scoped(self):
        refresh_alerts(notify=True)
        operator_notice = Notification.objects.get(user=self.operator)
        admin_notice = Notification.objects.get(user=self.admin)
        self.client.force_authenticate(self.operator)

        summary = self.client.get("/api/notifications/summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["unread_count"], 1)
        self.assertEqual(summary.data["total"], 1)

        read = self.client.post(f"/api/notifications/{operator_notice.id}/mark_read/")
        self.assertEqual(read.status_code, 200, read.data)
        self.assertTrue(read.data["read"])
        self.assertIsNotNone(read.data["read_at"])

        unread = self.client.post(f"/api/notifications/{operator_notice.id}/mark_unread/")
        self.assertEqual(unread.status_code, 200, unread.data)
        self.assertFalse(unread.data["read"])
        self.assertIsNone(unread.data["read_at"])

        forbidden = self.client.get(f"/api/notifications/{admin_notice.id}/")
        self.assertEqual(forbidden.status_code, 404)

        marked = self.client.post("/api/notifications/mark_all_read/")
        self.assertEqual(marked.status_code, 200, marked.data)
        self.assertEqual(marked.data["updated"], 1)

        cleared = self.client.delete("/api/notifications/clear_read/")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(cleared.data["deleted"], 0)
        self.assertEqual(cleared.data["preserved_active"], 1)
        self.assertTrue(Notification.objects.filter(pk=operator_notice.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=admin_notice.pk).exists())

    def test_summary_backfills_missing_notifications_without_reopening_read_items(self):
        refresh_alerts(notify=False)
        self.assertEqual(Notification.objects.count(), 0)

        self.client.force_authenticate(self.operator)
        first_summary = self.client.get("/api/notifications/summary/")
        self.assertEqual(first_summary.status_code, 200, first_summary.data)
        self.assertEqual(first_summary.data["unread_count"], 1)
        self.assertEqual(first_summary.data["active_alerts"], 1)
        self.assertEqual(Notification.objects.count(), 2)

        operator_notice = Notification.objects.get(user=self.operator)
        self.client.post(f"/api/notifications/{operator_notice.id}/mark_read/")

        unchanged_summary = self.client.get("/api/notifications/summary/")
        self.assertEqual(unchanged_summary.status_code, 200, unchanged_summary.data)
        self.assertEqual(unchanged_summary.data["unread_count"], 0)
        operator_notice.refresh_from_db()
        self.assertTrue(operator_notice.read)

        self.product.stock = Decimal("1")
        self.product.save(update_fields=["stock"])
        changed_summary = self.client.get("/api/notifications/summary/")
        self.assertEqual(changed_summary.data["unread_count"], 1)
        operator_notice.refresh_from_db()
        self.assertFalse(operator_notice.read)
        self.assertIn("1 unidade", operator_notice.message)

        self.product.stock = Decimal("10")
        self.product.save(update_fields=["stock"])
        resolved_summary = self.client.get("/api/notifications/summary/")
        self.assertEqual(resolved_summary.data["unread_count"], 0)
        self.assertEqual(resolved_summary.data["resolved_alerts"], 1)
        operator_notice.refresh_from_db()
        self.assertTrue(operator_notice.read)
        self.assertIsNotNone(operator_notice.read_at)

    def test_general_system_notifications_are_visible_and_user_scoped(self):
        from .services import notify_users

        created = notify_users(
            "Entrada confirmada",
            "A entrada ENT-001 foi confirmada.",
            level=Alert.INFO,
        )
        self.assertEqual(len(created), 2)

        self.client.force_authenticate(self.operator)
        response = self.client.get("/api/notifications/?alert_active=true&search=Entrada%20confirmada")
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["results"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Entrada confirmada")
        self.assertEqual(items[0]["source_display"], "Evento do sistema")
        self.assertEqual(items[0]["reference_display"], "Sistema")
        self.assertIsNone(items[0]["alert"])
