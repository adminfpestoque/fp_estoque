from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Category, Product, UserProfile

User = get_user_model()

class ProductTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin-products",
            password="AdminProducts123",
            is_staff=True,
            is_superuser=True,
        )
        
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )
        
        self.category = Category.objects.create(
            name="Refrigerantes",
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        
    def test_admin_can_create_product(self):
        response = self.client.post(
            "/api/products/",
            {
                "code": "REF-001",
                "name": "Coca-Cola 2L",
                "category": self.category.id,
                "cost_price": "8.50",
                "sale_price": "12.90",
                "minimum_stock": "10.000",
                "maximum_stock": "100.000",
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 201, response.data)
        
        product = Product.objects.get(code="REF-001")
        
        self.assertEqual(product.name, "Coca-Cola 2L")
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.cost_price, Decimal("8.50"))
        self.assertEqual(product.sale_price, Decimal("12.90"))
        
    def test_cannot_create_product_with_duplicate_code(self):
        Product.objects.create(
            code="REF-001",
            name="Produto existente",
            category=self.category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
        )
        
        response = self.client.post(
            "/api/products/",
            {
                "code": "REF-001",
                "name": "Coca-Cola 2L",
                "category": self.category.id,
                "cost_price": "6.00",
                "sale_price": "9.00",
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        
    def test_delete_product_only_deactivates_it(self):
        product = Product.objects.create(
            code="REF-002",
            name="Pepsi 2L",
            category=self.category,
            cost_price=Decimal("7.00"),
            sale_price=Decimal("11.00"),
        )
        
        response = self.client.delete(f"/api/products/{product.id}/")
        
        self.assertEqual(response.status_code, 204)
        
        product.refresh_from_db()
        
        self.assertFalse(product.active)
        self.assertTrue(Product.objects.filter(id=product.id).exists())
        
    def test_cannot_create_product_with_maximum_stock_less_than_minimum(self):
        response = self.client.post(
            "/api/products/",
            {
                "code": "REF-003",
                "name": "Produto inválido",
                "category": self.category.id,
                "minimum_stock": "20.000",
                "maximum_stock": "10.000",
                "cost_price": "5.00",
                "sale_price": "8.00",
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("maximum_stock", response.data)
        
    def test_low_stock_endpoint_returns_only_low_stock_products(self):
        Product.objects.create(
            code="LOW-001",
            name="Produto baixo",
            category=self.category,
            stock=Decimal("2.000"),
            minimum_stock=Decimal("5.000"),
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
        )
        
        Product.objects.create(
            code="OK-001",
            name="Produto normal",
            category=self.category,
            stock=Decimal("10.000"),
            minimum_stock=Decimal("5.000"),
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
        )
        
        response = self.client.get("/api/products/low_stock/")
        
        self.assertEqual(response.status_code, 200, response.data)
        
        names = [item["name"] for item in response.data["results"]]
        
        self.assertIn("Produto baixo", names)
        self.assertNotIn("Produto normal", names)
        
    def test_barcode_endpoint_returns_product(self):
        Product.objects.create(
            code="BAR-001",
            barcode="7891234567890",
            name="Produto com código de barras",
            category=self.category,
            cost_price=Decimal("5.00"),
            sale_price=Decimal("8.00"),
        )
        
        response = self.client.get(
            "/api/products/barcode/?value=7891234567890"
        )
        
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["barcode"], "7891234567890")
        self.assertEqual(response.data["name"], "Produto com código de barras")
        
    def test_barcode_endpoint_requires_value_parameter(self):
        response = self.client.get("/api/products/barcode/")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Informe o código de barras.",
        )
    
    def test_barcode_endpoint_returns_404_when_product_does_not_exist(self):
        response = self.client.get(
            "/api/products/barcode/?value=9999999999999"
        )
        
        self.assertEqual(response.status_code, 404)