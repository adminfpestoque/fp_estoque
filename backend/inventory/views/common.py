from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..permissions import RoleBasedPermission
from ..services import audit


def error_detail(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return getattr(exc, "messages", [str(exc)])


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "CREATE", instance, "Registro criado pela API.")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "UPDATE", instance, "Registro alterado pela API.")

    def perform_destroy(self, instance):
        if hasattr(instance, "active"):
            instance.active = False
            instance.save(update_fields=["active", "updated_at"])
            audit(self.request.user, "DEACTIVATE", instance, "Registro inativado.")
            return
        raise DjangoValidationError("Este registro não pode ser excluído. Utilize cancelamento ou estorno.")

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
