from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from .models import UserProfile
from datetime import date, timedelta
from django.utils import timezone
from decimal import Decimal
from .models import UserProfile, Product, Category, Lot

User = get_user_model()

class LotTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin-lots",
            password="AdminLots123",
            is_staff=True,
            is_superuser=True,
        )
    
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_lot_endpoint_is_read_only(self):
        response = self.client.post(
            "/api/lots/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_expiring_endpoint_returns_only_expiring_lots(self):
        category = Category.objects.create(
            name="Bebidas",
        )

        product = Product.objects.create(
            code="LOT-001",
            name="Produto Teste",
            category=category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
            minimum_stock=Decimal("10.000"),
            maximum_stock=Decimal("100.000"),
        )

        today = timezone.localdate()

        Lot.objects.create(
            product=product,
            number="LOTE-VALIDO",
            quantity=10,
            expiration_date=today + timedelta(days=10),
        )

        Lot.objects.create(
            product=product,
            number="LOTE-LONGE",
            quantity=10,
            expiration_date=today + timedelta(days=90),
        )

        response = self.client.get(
            "/api/lots/expiring/?days=30"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        numbers = [lot["number"] for lot in response.data]

        self.assertIn("LOTE-VALIDO", numbers)
        self.assertNotIn("LOTE-LONGE", numbers)

    def test_expired_endpoint_returns_only_expired_lots(self):
        category = Category.objects.create(
            name="Produtos Vencidos",
        )

        product = Product.objects.create(
            code="LOT-002",
            name="Produto Vencido Teste",
            category=category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
            minimum_stock=Decimal("10.000"),
            maximum_stock=Decimal("100.00"),
        )

        today = timezone.localdate()

        Lot.objects.create(
            product=product,
            number="LOTE-VENCIDO",
            quantity=10,
            expiration_date=today - timedelta(days=10)
        )

        Lot.objects.create(
            product=product,
            number="LOTE-VALIDO",
            quantity=10,
            expiration_date=today + timedelta(days=30),
        )

        response = self.client.get(
            "/api/lots/expired/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        numbers = [lot["number"] for lot in response.data]

        self.assertIn(
            "LOTE-VENCIDO",
            numbers,
        )

        self.assertNotIn(
            "LOTE-VALIDO",
            numbers,
        )

    def test_expired_endpoint_ignores_empty_lots(self):
        category = Category.objects.create(
            name="Teste Estoque Zero",
        )

        product = Product.objects.create(
            code="LOT-003",
            name="Produto Teste",
            category=category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
            minimum_stock=Decimal("10.000"),
            maximum_stock=Decimal("100.000"),
        )

        today = timezone.localdate()

        Lot.objects.create(
            product=product,
            number="LOTE-ZERO",
            quantity=0,
            expiration_date=today - timedelta(days=5)
        )

        response = self.client.get("/api/lots/expired/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        numbers = [lot["number"] for lot in response.data]

        self.assertNotIn("LOTE-ZERO", numbers)