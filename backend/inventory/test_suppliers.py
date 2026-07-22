from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import UserProfile

User = get_user_model()

class SupplierTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-suppliers",
            password="Admin12356!",
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
        
    def test_admin_can_create_supplier(self):
        response = self.client.post(
        "/api/suppliers/",
        {
            "name": "Fornecedor Teste",
            "document": "12345678000195",
            "email": "teste@fornecedor.com",
        },
        format="json",
    )
    
    def test_cannot_create_supplier_with_invalid_document(self):
        response = self.client.post(
            "/api/suppliers/",
            {
                "name": "Fornecedor Teste",
                "document": "1234567800019",
                "email": "teste@fornecedor.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("document", response.data)