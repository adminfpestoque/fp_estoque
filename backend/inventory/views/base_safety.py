from ..models import Alert
from ..safe_hooks import safe_audit
from . import common as common_views
from .alerts import AlertViewSet


# Os CRUDs que herdam BaseViewSet consultam a função audit no módulo common.
# Mantém a operação principal disponível mesmo se o registro auxiliar falhar.
common_views.audit = safe_audit

# Evita consultas extras ao serializar alertas ligados a saídas a prazo.
AlertViewSet.queryset = Alert.objects.select_related(
    "product",
    "lot",
    "inventory",
    "output",
)
