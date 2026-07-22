from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import UserProfile

User = get_user_model()


class UserCreationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-users",
            password="AdminUsers123!",
            is_superuser=True,
            is_staff=True,
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador de usuários",
            role=UserProfile.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_admin_creates_user_without_position(self):
        response = self.client.post(
            "/api/users/",
            {
                "username": "operador-novo",
                "email": "",
                "first_name": "",
                "last_name": "",
                "is_active": True,
                "full_name": "Operador Novo",
                "cpf": None,
                "phone": "",
                "role": UserProfile.OPERATOR,
                "profile_active": True,
                "password": "OperadorNovo123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username="operador-novo")
        self.assertEqual(user.inventory_profile.role, UserProfile.OPERATOR)
        self.assertEqual(user.inventory_profile.position, "")
        self.assertNotIn("position", response.data["profile"])

    def test_user_list_uses_valid_user_ordering(self):
        User.objects.create_user("z-operador", password="OperadorNovo123!")
        User.objects.create_user("a-operador", password="OperadorNovo123!")

        response = self.client.get("/api/users/?page=1")

        self.assertEqual(response.status_code, 200, response.data)
        usernames = [item["username"] for item in response.data["results"]]
        self.assertEqual(usernames, sorted(usernames))

    def test_user_creation_returns_password_validation_message(self):
        response = self.client.post(
            "/api/users/",
            {
                "username": "senha-fraca",
                "full_name": "Senha Fraca",
                "role": UserProfile.OPERATOR,
                "profile_active": True,
                "is_active": True,
                "password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
