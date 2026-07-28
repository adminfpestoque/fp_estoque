from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class NotificationCleanupMigrationTests(TransactionTestCase):
    migrate_from = ("inventory", "0019_clear_products_entries_outputs")
    migrate_to = ("inventory", "0020_clear_notifications")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        User = get_user_model()
        user = User.objects.create_user(
            username="notification-cleanup-user",
            password="safe-password",
        )
        Alert = old_apps.get_model("inventory", "Alert")
        Notification = old_apps.get_model("inventory", "Notification")
        SystemSetting = old_apps.get_model("inventory", "SystemSetting")

        alert = Alert.objects.create(
            type="LOW_STOCK",
            level="WARNING",
            message="Alerta preservado",
            active=True,
        )
        Notification.objects.create(
            user_id=user.pk,
            alert=alert,
            title="Notificação de alerta",
            message="Deve ser apagada",
            level="WARNING",
        )
        Notification.objects.create(
            user_id=user.pk,
            title="Evento geral",
            message="Também deve ser apagado",
            level="INFO",
        )
        SystemSetting.objects.create(
            key="notification_cleanup_setting",
            value="preservar",
            description="Configuração que deve permanecer",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps
        self.user_id = user.pk

    def test_only_notifications_are_removed(self):
        Alert = self.apps.get_model("inventory", "Alert")
        Notification = self.apps.get_model("inventory", "Notification")
        SystemSetting = self.apps.get_model("inventory", "SystemSetting")
        User = get_user_model()

        self.assertEqual(Notification.objects.count(), 0)
        self.assertTrue(Alert.objects.filter(message="Alerta preservado").exists())
        self.assertTrue(
            SystemSetting.objects.filter(key="notification_cleanup_setting").exists()
        )
        self.assertTrue(User.objects.filter(pk=self.user_id).exists())
