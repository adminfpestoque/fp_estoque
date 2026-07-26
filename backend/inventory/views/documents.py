from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from ..models import Alert, Movement, StockAdjustment, StockEntry, StockOutput
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import MovementSerializer, StockAdjustmentSerializer, StockEntrySerializer, StockOutputSerializer
from ..services import audit, notify_users, refresh_alerts
from .common import BaseViewSet, error_detail


class SoftDeletedDocumentViewSet(BaseViewSet):
    deleted_label = "registro"

    def get_queryset(self):
        queryset = super().get_queryset()
        deleted = self.request.query_params.get("deleted")
        if deleted == "true":
            queryset = queryset.filter(deleted_at__isnull=False)
        elif deleted == "false":
            queryset = queryset.filter(deleted_at__isnull=True)
        return queryset

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        try:
            document.soft_delete(request.user, request.data.get("reason") or "")
            refresh_alerts(notify=True)
            audit(
                request.user,
                "SOFT_DELETE",
                document,
                f"{self.deleted_label.capitalize()} {document.number} excluída logicamente.",
                metadata={"number": document.number, "reason": document.deletion_reason},
            )
            notify_users(
                f"{self.deleted_label.capitalize()} excluída",
                (
                    f"A {self.deleted_label} {document.number} foi excluída por "
                    f"{request.user.username}. O registro permanece no histórico."
                ),
                level=Alert.WARNING,
            )
            document.refresh_from_db()
            return Response(self.get_serializer(document).data, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)


class StockEntryViewSet(SoftDeletedDocumentViewSet):
    queryset = StockEntry.objects.select_related(
        "supplier", "user", "cancelled_by", "deleted_by"
    ).prefetch_related("items__product", "items__lot")
    serializer_class = StockEntrySerializer
    filterset_fields = ["status", "supplier", "user"]
    search_fields = [
        "number",
        "invoice_number",
        "supplier__name",
        "notes",
        "items__product__name",
        "items__product_name_snapshot",
    ]
    ordering_fields = ["entry_date", "total_value", "created_at", "deleted_at"]
    deleted_label = "entrada"

    def perform_update(self, serializer):
        entry = serializer.save()
        refresh_alerts(notify=True)
        audit(self.request.user, "UPDATE", entry, f"Entrada {entry.number} atualizada.")
        notify_users(
            "Entrada atualizada",
            f"A entrada {entry.number} foi atualizada por {self.request.user.username}.",
            level=Alert.INFO,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.confirm(request.user)
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", entry, f"Entrada {entry.number} confirmada.")
            notify_users(
                "Entrada confirmada",
                f"A entrada {entry.number} do fornecedor {entry.supplier} foi confirmada por {request.user.username}.",
                level=Alert.INFO,
            )
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
            notify_users(
                "Entrada cancelada",
                f"A entrada {entry.number} foi cancelada e o estoque correspondente foi estornado por {request.user.username}.",
                level=Alert.WARNING,
            )
            return Response(self.get_serializer(entry).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class StockOutputViewSet(SoftDeletedDocumentViewSet):
    queryset = StockOutput.objects.select_related(
        "user", "cancelled_by", "deleted_by"
    ).prefetch_related("items__product", "items__lot", "items__packaging")
    serializer_class = StockOutputSerializer
    filterset_fields = ["status", "reason", "payment_method", "user"]
    search_fields = [
        "number",
        "customer_name",
        "payment_reference",
        "notes",
        "items__product__name",
        "items__product_name_snapshot",
    ]
    ordering_fields = ["output_date", "total_value", "created_at", "deleted_at"]
    deleted_label = "saída"

    def perform_update(self, serializer):
        output = serializer.save()
        refresh_alerts(notify=True)
        audit(self.request.user, "UPDATE", output, f"Saída {output.number} atualizada.")
        notify_users(
            "Saída atualizada",
            f"A saída {output.number} foi atualizada por {self.request.user.username}.",
            level=Alert.INFO,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        output = self.get_object()
        try:
            output.confirm(request.user, require_payment=True)
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", output, f"Saída {output.number} confirmada.")
            notify_users(
                "Saída confirmada",
                f"A saída {output.number} foi confirmada por {request.user.username}.",
                level=Alert.INFO,
            )
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
            notify_users(
                "Saída cancelada",
                f"A saída {output.number} foi cancelada e o estoque correspondente foi devolvido por {request.user.username}.",
                level=Alert.WARNING,
            )
            return Response(self.get_serializer(output).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)


class MovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsInventoryUser]
    serializer_class = MovementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type", "product", "lot", "user", "reversed"]
    search_fields = ["product__name", "product__code", "product_name_snapshot", "product_code_snapshot", "reason", "document", "notes", "user__username"]
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
            notify_users(
                "Movimentação estornada",
                f"A movimentação #{movement.pk} de {movement.product_name} foi estornada por {request.user.username}.",
                level=Alert.WARNING,
            )
            return Response(self.get_serializer(reversal).data, status=201)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)



class StockAdjustmentViewSet(BaseViewSet):
    queryset = StockAdjustment.objects.select_related(
        "product",
        "product__category",
        "lot",
        "user",
        "movement",
    )
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAdministrator]
    filterset_fields = ["status", "type", "product", "lot", "user"]
    search_fields = [
        "number",
        "product__name",
        "product__code",
        "reason",
        "justification",
    ]
    ordering_fields = ["created_at", "quantity", "confirmed_at", "cancelled_at"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            queryset = queryset.filter(created_at__date__gte=start)
        if end:
            queryset = queryset.filter(created_at__date__lte=end)
        return queryset

    def perform_create(self, serializer):
        adjustment = serializer.save()
        audit(
            self.request.user,
            "CREATE",
            adjustment,
            f"Ajuste {adjustment.number} criado como rascunho.",
        )

    def perform_update(self, serializer):
        adjustment = serializer.save()
        audit(
            self.request.user,
            "UPDATE",
            adjustment,
            f"Rascunho do ajuste {adjustment.number} atualizado.",
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        values = queryset.aggregate(
            total=Count("id"),
            drafts=Count("id", filter=Q(status=StockAdjustment.DRAFT)),
            confirmed=Count("id", filter=Q(status=StockAdjustment.CONFIRMED)),
            cancelled=Count("id", filter=Q(status=StockAdjustment.CANCELLED)),
            positive_quantity=Sum(
                "quantity",
                filter=Q(
                    status=StockAdjustment.CONFIRMED,
                    type=StockAdjustment.POSITIVE,
                ),
            ),
            negative_quantity=Sum(
                "quantity",
                filter=Q(
                    status=StockAdjustment.CONFIRMED,
                    type=StockAdjustment.NEGATIVE,
                ),
            ),
        )
        values["positive_quantity"] = values["positive_quantity"] or 0
        values["negative_quantity"] = values["negative_quantity"] or 0
        return Response(values)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        adjustment = self.get_object()
        try:
            adjustment.confirm(request.user)
            adjustment.refresh_from_db()
            refresh_alerts(notify=True)
            audit(request.user, "CONFIRM", adjustment, f"Ajuste {adjustment.number} confirmado.")
            notify_users(
                "Ajuste de estoque confirmado",
                f"O ajuste {adjustment.number} de {adjustment.product.name} foi confirmado por {request.user.username}.",
                level=Alert.WARNING,
            )
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        adjustment = self.get_object()
        try:
            adjustment.cancel(request.user)
            adjustment.refresh_from_db()
            refresh_alerts(notify=True)
            audit(request.user, "CANCEL", adjustment, f"Ajuste {adjustment.number} cancelado e estornado.")
            notify_users(
                "Ajuste de estoque cancelado",
                f"O ajuste {adjustment.number} foi cancelado e estornado por {request.user.username}.",
                level=Alert.INFO,
            )
            return Response(self.get_serializer(adjustment).data)
        except DjangoValidationError as exc:
            return Response({"detail": error_detail(exc)}, status=400)
