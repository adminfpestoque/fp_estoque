from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Notification


class RenderRecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="render-recovery-admin",
            password="RenderRecovery123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_notification_summary_survives_alert_refresh_failure(self):
        Notification.objects.create(
            user=self.user,
            title="Evento preservado",
            message="Evento geral do sistema.",
            level="INFO",
        )

        with patch(
            "inventory.safe_hooks.refresh_alerts",
            side_effect=RuntimeError("falha simulada durante atualização de alertas"),
        ):
            response = self.client.get("/api/notifications/summary/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["system_events"], 1)
