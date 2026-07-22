from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..models import InventoryCount, InventoryItem, Movement, Product, StockAdjustment, StockEntry, StockOutput
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import InventoryItemSerializer, InventorySerializer, MovementSerializer, StockAdjustmentSerializer, StockEntrySerializer, StockOutputSerializer
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
            refresh_alerts(notify=False)
            audit(request.user, "CONFIRM", entry, f"Entrada {entry.number} confirmada.")
            return Response(self.get_serializer(entry).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def cancel(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.cancel(request.user)
            refresh_alerts(notify=False)
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
            refresh_alerts(notify=False)
            audit(request.user, "CONFIRM", output, f"Saída {output.number} confirmada.")
            return Response(self.get_serializer(output).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def cancel(self, request, pk=None):
        output = self.get_object()
        try:
            output.cancel(request.user)
            refresh_alerts(notify=False)
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
            refresh_alerts(notify=False)
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
            refresh_alerts(notify=False)
            audit(request.user, "CONFIRM", adjustment, f"Ajuste {adjustment.number} confirmado.")
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        adjustment = self.get_object()
        try:
            adjustment.cancel(request.user)
            refresh_alerts(notify=False)
            audit(request.user, "CANCEL", adjustment, f"Ajuste {adjustment.number} cancelado.")
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class InventoryViewSet(BaseViewSet):
    queryset = InventoryCount.objects.select_related("user", "category").prefetch_related("items__product")
    serializer_class = InventorySerializer
    filterset_fields = ["status", "category", "user"]
    search_fields = ["number", "notes"]
    ordering_fields = ["started_at", "completed_at", "created_at"]

    def perform_create(self, serializer):
        inventory = serializer.save(user=self.request.user)
        products = Product.objects.filter(active=True)
        if inventory.category:
            products = products.filter(category=inventory.category)
        if self.request.data.get("populate", True):
            InventoryItem.objects.bulk_create([
                InventoryItem(inventory=inventory, product=p, system_quantity=p.stock, counted_quantity=p.stock)
                for p in products
            ])
        audit(self.request.user, "CREATE", inventory, "Inventário iniciado.")

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        inventory = self.get_object()
        if inventory.status not in {InventoryCount.OPEN, InventoryCount.WAITING}:
            return Response({"detail": "Este inventário não aceita alterações."}, status=400)
        product = Product.objects.filter(pk=request.data.get("product")).first()
        if not product:
            return Response({"product": "Produto não encontrado."}, status=400)
        counted = request.data.get("counted_quantity")
        if counted is None:
            return Response({"counted_quantity": "Informe a quantidade contada."}, status=400)
        item, _ = InventoryItem.objects.update_or_create(
            inventory=inventory,
            product=product,
            defaults={
                "system_quantity": product.stock,
                "counted_quantity": counted,
                "justification": request.data.get("justification", ""),
            },
        )
        return Response(InventoryItemSerializer(item).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        inventory = self.get_object()
        if inventory.status != InventoryCount.OPEN:
            return Response({"detail": "Somente inventários em andamento podem ser enviados."}, status=400)
        inventory.status = InventoryCount.WAITING
        inventory.save(update_fields=["status", "updated_at"])
        audit(request.user, "SUBMIT", inventory, "Inventário enviado para confirmação.")
        return Response(self.get_serializer(inventory).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def conclude(self, request, pk=None):
        inventory = self.get_object()
        try:
            inventory.conclude(request.user)
            refresh_alerts(notify=False)
            audit(request.user, "CONCLUDE", inventory, "Inventário concluído e divergências ajustadas.")
            return Response(self.get_serializer(inventory).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        inventory = self.get_object()
        if inventory.status == InventoryCount.DONE:
            return Response({"detail": "Inventário concluído não pode ser cancelado."}, status=400)
        inventory.status = InventoryCount.CANCELLED
        inventory.save(update_fields=["status", "updated_at"])
        audit(request.user, "CANCEL", inventory, "Inventário cancelado.")
        return Response(self.get_serializer(inventory).data)
