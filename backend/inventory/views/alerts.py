from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..models import Alert, AuditLog, Notification, SystemSetting
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import AlertSerializer, AuditLogSerializer, NotificationSerializer, SystemSettingSerializer
from ..services import audit, refresh_alerts
from .common import BaseViewSet


class AlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsInventoryUser]
    serializer_class = AlertSerializer
    queryset = Alert.objects.select_related("product", "lot", "inventory")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["active", "type", "level", "product", "lot"]
    search_fields = ["message", "product__name", "lot__number"]
    ordering = ["-active", "-created_at"]

    @action(detail=False, methods=["post"], permission_classes=[IsAdministrator])
    def refresh(self, request):
        alerts = refresh_alerts(notify=True)
        audit(request.user, "REFRESH_ALERTS", description=f"{len(alerts)} alertas recalculados.")
        return Response({"created": len(alerts), "alerts": self.get_serializer(alerts, many=True).data})


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsInventoryUser]
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["read", "level"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related("alert")

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["read", "read_at", "updated_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        count = self.get_queryset().filter(read=False).update(read=True, read_at=timezone.now())
        return Response({"updated": count})


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdministrator]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("user")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["action", "entity", "user"]
    search_fields = ["description", "object_id", "user__username"]
    ordering = ["-created_at"]


class SystemSettingViewSet(BaseViewSet):
    permission_classes = [IsAdministrator]
    serializer_class = SystemSettingSerializer
    queryset = SystemSetting.objects.all()
    search_fields = ["key", "description"]
    lookup_field = "key"
