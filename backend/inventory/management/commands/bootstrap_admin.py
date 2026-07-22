import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import UserProfile


class Command(BaseCommand):
    help = "Cria ou atualiza o administrador inicial do FP Estoque."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None)
        parser.add_argument("--email", default=None)
        parser.add_argument("--password", default=None)
        parser.add_argument("--full-name", default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        username = (options["username"] or os.getenv("ADMIN_USERNAME") or "admin").strip()
        email = (options["email"] or os.getenv("ADMIN_EMAIL") or "").strip()
        full_name = (options["full_name"] or os.getenv("ADMIN_FULL_NAME") or "Administrador FP Estoque").strip()
        password = options["password"] or os.getenv("ADMIN_PASSWORD")
        if not username:
            raise CommandError("O nome de usuário não pode ficar vazio.")
        if not password:
            password = getpass.getpass("Senha do administrador: ")
            confirmation = getpass.getpass("Confirme a senha: ")
            if password != confirmation:
                raise CommandError("As senhas informadas não são iguais.")
        if len(password) < 8:
            raise CommandError("Utilize uma senha com pelo menos 8 caracteres.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name, "role": UserProfile.ADMIN, "active": True},
        )
        action = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(f"Administrador '{username}' {action} com sucesso."))
