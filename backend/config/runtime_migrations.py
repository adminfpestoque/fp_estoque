import logging
import os

from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

# Identificador fixo usado apenas para serializar migrations entre workers Gunicorn.
_MIGRATION_LOCK_ID = 726984321


def run_startup_migrations():
    """Apply pending Django migrations before the WSGI process starts serving."""
    disabled = str(os.environ.get("SKIP_STARTUP_MIGRATIONS", "")).strip().lower()
    if disabled in {"1", "true", "yes", "on"}:
        logger.warning("Migrations automáticas de inicialização foram desativadas.")
        return

    if connection.vendor != "postgresql":
        call_command("migrate", interactive=False, verbosity=1)
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [_MIGRATION_LOCK_ID])

    try:
        call_command("migrate", interactive=False, verbosity=1)
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [_MIGRATION_LOCK_ID])
        except Exception:
            logger.exception("Não foi possível liberar o bloqueio das migrations.")
