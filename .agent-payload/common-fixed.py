from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..permissions import RoleBasedPermission
from ..services import audit


def error_detail(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return getattr(exc, "messages", [str(exc)])


class BaseViewSet(viewsets.ModelViewSet):
    """Base CRUD view with explicit governance rules.

    Permanent deletion is denied by default. Master-data viewsets may opt in to
    activate/deactivate actions by setting ``supports_activation = True``.
    """

    permission_classes = [RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering = ["-created_at"]
    supports_activation = False
    activation_field = "active"
    governance_name = "registro"

    def perform_create(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "CREATE", instance, "Registro criado pela API.")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "UPDATE", instance, "Registro alterado pela API.")

    def after_activation_change(self, instance, active):
        """Hook for viewsets that need side effects after a status change."""

    def _set_activation(self, request, active):
        if not self.supports_activation:
            return Response(
                {
                    "detail": (
                        "Este tipo de registro não possui ativação manual. "
                        "Registros históricos devem ser preservados e tratados por cancelamento, estorno ou conclusão."
                    )
                },
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        instance = self.get_object()
        field = self.activation_field
        current = bool(getattr(instance, field, False))

        if current != active:
            setattr(instance, field, active)
            update_fields = [field]
            if hasattr(instance, "updated_at"):
                update_fields.append("updated_at")
            instance.save(update_fields=update_fields)
            audit(
                request.user,
                "ACTIVATE" if active else "DEACTIVATE",
                instance,
                f"Status de {self.governance_name} alterado para {'ativo' if active else 'inativo'}.",
            )
            self.after_activation_change(instance, active)

        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        return self._set_activation(request, True)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return self._set_activation(request, False)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    f"A exclusão permanente de {self.governance_name} não é permitida. "
                    "Utilize a ação de inativar quando disponível; registros históricos devem ser preservados."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
