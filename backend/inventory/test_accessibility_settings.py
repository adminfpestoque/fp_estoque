from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Alert, Category, Product, SystemSetting, UserProfile
from .services import refresh_alerts

User = get_user_model()


class AccessibilityAndUserStatusTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "access-admin",
            email="access-admin@example.com",
            password="AccessAdmin123!",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador de acessibilidade",
            role=UserProfile.OPERATOR,
            active=True,
        )
        self.operator = User.objects.create_user(
            "access-operator",
            password="AccessOperator123!",
            is_active=False,
        )
        UserProfile.objects.create(
            user=self.operator,
            full_name="Operador inativo",
            role=UserProfile.OPERATOR,
            active=False,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_activation_response_and_list_use_the_effective_status(self):
        response = self.client.post(f"/api/users/{self.operator.id}/activate/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_active"])
        self.assertTrue(response.data["profile"]["active"])
        self.assertTrue(response.data["effective_active"])

        listed = self.client.get("/api/users/")
        self.assertEqual(listed.status_code, 200, listed.data)
        rows = listed.data.get("results", listed.data)
        row = next(item for item in rows if item["id"] == self.operator.id)
        self.assertTrue(row["effective_active"])

    def test_superuser_is_presented_as_administrator_even_with_legacy_profile_role(self):
        response = self.client.get("/api/users/me/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["effective_role"], UserProfile.ADMIN)
        self.assertEqual(response.data["permissions"]["role"], UserProfile.ADMIN)

    def test_current_user_can_save_accessibility_preferences(self):
        response = self.client.patch(
            "/api/users/me/",
            {
                "theme": UserProfile.THEME_HIGH_CONTRAST,
                "font_scale": UserProfile.FONT_EXTRA_LARGE,
                "reduced_motion": True,
                "enhanced_focus": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.admin.inventory_profile.refresh_from_db()
        self.assertEqual(self.admin.inventory_profile.theme, UserProfile.THEME_HIGH_CONTRAST)
        self.assertEqual(self.admin.inventory_profile.font_scale, UserProfile.FONT_EXTRA_LARGE)
        self.assertTrue(self.admin.inventory_profile.reduced_motion)
        self.assertEqual(response.data["profile"]["theme"], UserProfile.THEME_HIGH_CONTRAST)

    def test_stock_alert_setting_is_applied(self):
        category = Category.objects.create(name="Bebidas de teste")
        product = Product.objects.create(
            code="ACCESS-001",
            name="Produto sem estoque",
            category=category,
            stock=Decimal("0"),
            minimum_stock=Decimal("2"),
        )
        SystemSetting.objects.create(key="stock_alerts_enabled", value="false")
        refresh_alerts(notify=False)
        self.assertFalse(Alert.objects.filter(product=product, active=True).exists())

        setting = SystemSetting.objects.get(key="stock_alerts_enabled")
        setting.value = "true"
        setting.save(update_fields=["value", "updated_at"])
        refresh_alerts(notify=False)
        self.assertTrue(
            Alert.objects.filter(product=product, type=Alert.OUT_OF_STOCK, active=True).exists()
        )
