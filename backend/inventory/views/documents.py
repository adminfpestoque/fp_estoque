from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..models import Movement, StockAdjustment, StockEntry, StockOutput
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import MovementSerializer, StockAdjustmentSerializer, StockEntrySerializer, StockOutputSerializer
from ..services import audit, refresh_alerts
from .common import BaseViewSet, error_detail


class StockEntryViewSet(BaseViewSet):
    queryset = StockEntry.objects.select_related("supplier", "user", "cancelled_by").prefetch_related("items__product", "items__lot")
    serializer_class = StockEntrySerializer
    filterset_fields = ["status", "supplier", "user"]
    search_fields = ["number", "invoice_number", "supplier__name", "notes"]
    ordering_fields = ["entry_date", "total_value", "created_at"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.confirm(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", entry, f"Entrada {entry.number} confirmada.")
            return Response(self.get_serializer(entry).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def cancel(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.cancel(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CANCEL", entry, f"Entrada {entry.number} cancelada e estornada.")
            return Response(self.get_serializer(entry).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class StockOutputViewSet(BaseViewSet):
    queryset = StockOutput.objects.select_related("user", "cancelled_by").prefetch_related("items__product", "items__lot")
    serializer_class = StockOutputSerializer
    filterset_fields = ["status", "reason", "user"]
    search_fields = ["number", "notes", "items__product__name"]
    ordering_fields = ["output_date", "created_at"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        output = self.get_object()
        try:
            output.confirm(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", output, f"Saída {output.number} confirmada.")
            return Response(self.get_serializer(output).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def cancel(self, request, pk=None):
        output = self.get_object()
        try:
            output.cancel(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CANCEL", output, f"Saída {output.number} cancelada e estornada.")
            return Response(self.get_serializer(output).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class MovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsInventoryUser]
    serializer_class = MovementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type", "product", "lot", "user", "reversed"]
    search_fields = ["product__name", "product__code", "reason", "document", "notes", "user__username"]
    ordering_fields = ["created_at", "quantity", "unit_cost", "final_stock"]
    ordering = ["-created_at"]
    queryset = Movement.objects.select_related("product", "product__category", "lot", "user").all()

    def get_queryset(self):
        qs = super().get_queryset()
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def reverse(self, request, pk=None):
        movement = self.get_object()
        try:
            reversal = Movement.reverse(original=movement, user=request.user, reason=request.data.get("reason") or "Estorno manual")
            refresh_alerts(notify=True)
            audit(request.user, "REVERSE", movement, f"Movimentação #{movement.pk} estornada.")
            return Response(self.get_serializer(reversal).data, status=201)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class StockAdjustmentViewSet(BaseViewSet):
    queryset = StockAdjustment.objects.select_related("product", "lot", "user", "movement")
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAdministrator]
    filterset_fields = ["status", "type", "product", "lot", "user"]
    search_fields = ["number", "product__name", "reason", "justification"]
    ordering_fields = ["created_at", "quantity"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        adjustment = self.get_object()
        try:
            adjustment.confirm(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", adjustment, f"Ajuste {adjustment.number} confirmado.")
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        adjustment = self.get_object()
        try:
            adjustment.cancel(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CANCEL", adjustment, f"Ajuste {adjustment.number} cancelado.")
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)
