from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Category, UserProfile

User = get_user_model()

class CategoryTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-category",
            password="AdminCategory123!",
            is_staff=True,
            is_superuser=True,
        )

        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador",
            role=UserProfile.ADMIN,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_category(self):
        response = self.client.post(
            "/api/categories/",
            {
                "name": "Cervejas",
                "description": "Categoria de bebidas",
                "active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Category.objects.filter(name="Cervejas").exists())

    def test_cannot_create_duplicate_category(self):
        Category.objects.create(
            name="Cervejas",
            description="Categoria existente",
        )

        response = self.client.post(
            "/api/categories/",
            {
                "name": "Cervejas",
                "description": "Duplicada",
                "active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_delete_category_only_deactivates_it(self):
        category = Category.objects.create(
            name="Descartáveis",
            description="Produtos descartáveis",
        )

        response = self.client.delete(f"/api/categories/{category.id}/")

        self.assertEqual(response.status_code, 204)

        category.refresh_from_db()
        self.assertFalse(category.active)

    def test_category_list_is_sorted_by_name(self):
        Category.objects.create(name="Zebra")
        Category.objects.create(name="Abacaxi")
        Category.objects.create(name="Banana")

        response = self.client.get("/api/categories/")

        self.assertEqual(response.status_code, 200, response.data)

        names = [item["name"] for item in response.data["results"]]

        self.assertEqual(names, sorted(names))