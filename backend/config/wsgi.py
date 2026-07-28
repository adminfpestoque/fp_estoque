import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# O serviço gratuito da Render está configurado para iniciar diretamente pelo
# Gunicorn. As migrations precisam ser aplicadas aqui antes de aceitar requisições.
from .runtime_migrations import run_startup_migrations  # noqa: E402

run_startup_migrations()
