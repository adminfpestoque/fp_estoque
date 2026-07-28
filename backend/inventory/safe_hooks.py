import logging

from .services import audit, notify_users, refresh_alerts

logger = logging.getLogger(__name__)


def safe_audit(*args, **kwargs):
    """Registra auditoria sem bloquear a operação principal em caso de falha auxiliar."""
    try:
        return audit(*args, **kwargs)
    except Exception:
        logger.exception("Falha ao registrar auditoria do estoque.")
        return None


def safe_notify_users(*args, **kwargs):
    """Gera notificações sem transformar uma falha auxiliar em erro 500 operacional."""
    try:
        return notify_users(*args, **kwargs)
    except Exception:
        logger.exception("Falha ao gerar notificações do estoque.")
        return []


def safe_refresh_alerts(*args, **kwargs):
    """Sincroniza alertas de forma isolada da confirmação de entradas e saídas."""
    try:
        return refresh_alerts(*args, **kwargs)
    except Exception:
        logger.exception("Falha ao sincronizar alertas do estoque.")
        return []
