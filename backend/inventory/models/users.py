from django.conf import settings
from django.db import models

from .base import TimeStamped

class UserProfile(TimeStamped):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ROLES = [(ADMIN, "Administrador"), (OPERATOR, "Operador de estoque")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_profile",
    )
    full_name = models.CharField(max_length=180)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    position = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=10, choices=ROLES, default=OPERATOR)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name", "user__username"]

    def __str__(self):
        return self.full_name or self.user.username


