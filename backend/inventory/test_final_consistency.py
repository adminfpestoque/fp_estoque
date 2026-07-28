from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import StockOutput
from .serializers import StockOutputSerializer


class FinalConsistencyTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="final-consistency-admin",
            password="FinalConsistency123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_base_crud_is_not_blocked_when_audit_fails(self):
        with patch(
            "inventory.safe_hooks.audit",
            side_effect=RuntimeError("falha simulada na auditoria"),
        ):
            response = self.client.post(
                "/api/categories/",
                {
                    "name": "Categoria criada com auditoria indisponível",
                    "description": "Teste de isolamento da auditoria.",
                    "active": True,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            response.data["name"],
            "Categoria criada com auditoria indisponível",
        )

    def test_cancelled_credit_output_is_not_reported_as_pending(self):
        output = StockOutput.objects.create(
            user=self.user,
            reason="COMMERCIAL",
            customer_name="Cliente cancelado",
            payment_method=StockOutput.PAYMENT_ON_ACCOUNT,
            payment_due_date=timezone.localdate() + timedelta(days=5),
            status=StockOutput.CANCELLED,
        )

        self.assertEqual(output.payment_status, "CANCELLED")
        self.assertEqual(output.payment_status_display, "Cancelado")
        self.assertFalse(output.payment_overdue)

        data = StockOutputSerializer(output).data
        self.assertEqual(data["payment_status"], "CANCELLED")
        self.assertEqual(data["payment_status_display"], "Cancelado")
        self.assertFalse(data["payment_overdue"])

    def test_temporary_alert_failure_does_not_break_category_creation(self):
        with patch(
            "inventory.safe_hooks.refresh_alerts",
            side_effect=RuntimeError("falha simulada nos alertas"),
        ):
            response = self.client.post(
                "/api/categories/",
                {"name": "Categoria sem dependência de alertas", "active": True},
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.data)
