from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from ..models import InventoryCount, InventoryItem, Product
from ..permissions import IsAdministrator
from ..serializers import InventoryItemSerializer, InventorySerializer
from ..services import audit, refresh_alerts
from .common import BaseViewSet, error_detail


class InventoryViewSet(BaseViewSet):
    queryset = InventoryCount.objects.select_related(
        "user",
        "category",
        "submitted_by",
        "completed_by",
        "cancelled_by",
    ).prefetch_related(
        "items__product",
        "items__product__category",
        "items__counted_by",
        "items__adjustment_movement",
    )
    serializer_class = InventorySerializer
    filterset_fields = ["status", "category", "user"]
    search_fields = [
        "number",
        "notes",
        "items__product__name",
        "items__product__code",
    ]
    ordering_fields = ["started_at", "submitted_at", "completed_at", "created_at"]
    ordering = ["-started_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            queryset = queryset.filter(started_at__date__gte=start)
        if end:
            queryset = queryset.filter(started_at__date__lte=end)
        return queryset.distinct()

    def perform_create(self, serializer):
        category = serializer.validated_data.get("category")
        active = InventoryCount.objects.filter(
            status__in=[InventoryCount.OPEN, InventoryCount.WAITING]
        )
        if category:
            active = active.filter(Q(category__isnull=True) | Q(category=category))
        if active.exists():
            raise DRFValidationError(
                {
                    "detail": (
                        "Já existe um inventário em andamento que abrange os produtos "
                        "selecionados. Conclua ou cancele o inventário atual primeiro."
                    )
                }
            )

        inventory = serializer.save(user=self.request.user)
        products = Product.objects.filter(active=True).select_related("category")
        if inventory.category:
            products = products.filter(category=inventory.category)
        if self.request.data.get("populate", True):
            InventoryItem.objects.bulk_create(
                [
                    InventoryItem(
                        inventory=inventory,
                        product=product,
                        system_quantity=product.stock,
                        counted_quantity=product.stock,
                        counted=False,
                    )
                    for product in products
                ]
            )
        audit(self.request.user, "CREATE", inventory, "Inventário iniciado.")

    def _record_item(self, inventory, payload, user):
        if inventory.status != InventoryCount.OPEN:
            raise DRFValidationError(
                {"detail": "Somente inventários em andamento aceitam contagens."}
            )

        product = Product.objects.filter(pk=payload.get("product"), active=True).first()
        if not product:
            raise DRFValidationError({"product": "Produto não encontrado ou inativo."})
        if inventory.category_id and product.category_id != inventory.category_id:
            raise DRFValidationError(
                {"product": "O produto não pertence à categoria deste inventário."}
            )

        raw_counted = payload.get("counted_quantity")
        if raw_counted in (None, ""):
            raise DRFValidationError(
                {"counted_quantity": "Informe a quantidade física contada."}
            )
        try:
            counted = Decimal(str(raw_counted))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise DRFValidationError(
                {"counted_quantity": "Informe uma quantidade válida."}
            ) from exc
        if counted < 0:
            raise DRFValidationError(
                {"counted_quantity": "A quantidade contada não pode ser negativa."}
            )

        product.refresh_from_db(fields=["stock", "updated_at"])
        justification = str(payload.get("justification") or "").strip()
        difference = counted - product.stock
        if difference and not justification:
            raise DRFValidationError(
                {"justification": f"Justifique a divergência do produto {product.name}."}
            )

        item, _ = InventoryItem.objects.update_or_create(
            inventory=inventory,
            product=product,
            defaults={
                "system_quantity": product.stock,
                "counted_quantity": counted,
                "counted": True,
                "counted_at": timezone.now(),
                "counted_by": user,
                "justification": justification,
            },
        )
        return item

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        inventory = self.get_object()
        try:
            item = self._record_item(inventory, request.data, request.user)
            audit(
                request.user,
                "COUNT_ITEM",
                inventory,
                f"Contagem registrada para {item.product.name}.",
            )
            return Response(InventoryItemSerializer(item).data)
        except DRFValidationError as exc:
            return Response(exc.detail, status=400)

    @action(detail=True, methods=["post"])
    def bulk_count(self, request, pk=None):
        inventory = self.get_object()
        payload_items = request.data.get("items")
        if not isinstance(payload_items, list) or not payload_items:
            return Response({"items": "Informe pelo menos uma contagem."}, status=400)
        try:
            with transaction.atomic():
                saved = [
                    self._record_item(inventory, payload, request.user)
                    for payload in payload_items
                ]
            audit(
                request.user,
                "COUNT_ITEMS",
                inventory,
                f"{len(saved)} contagem(ns) registrada(s).",
            )
            refreshed = self.get_queryset().get(pk=inventory.pk)
            return Response(self.get_serializer(refreshed).data)
        except DRFValidationError as exc:
            return Response(exc.detail, status=400)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        inventory = self.get_object()
        try:
            inventory.submit(request.user)
            audit(request.user, "SUBMIT", inventory, "Inventário enviado para confirmação.")
            return Response(self.get_serializer(inventory).data)
        except Exception as exc:
            if hasattr(exc, "messages"):
                return Response({"detail": error_detail(exc)}, status=400)
            raise

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def reopen(self, request, pk=None):
        inventory = self.get_object()
        try:
            inventory.reopen()
            audit(request.user, "REOPEN", inventory, "Inventário reaberto para conferência.")
            return Response(self.get_serializer(inventory).data)
        except Exception as exc:
            if hasattr(exc, "messages"):
                return Response({"detail": error_detail(exc)}, status=400)
            raise

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def conclude(self, request, pk=None):
        inventory = self.get_object()
        try:
            inventory.conclude(request.user)
            refresh_alerts(notify=False)
            audit(
                request.user,
                "CONCLUDE",
                inventory,
                "Inventário concluído e divergências ajustadas.",
            )
            return Response(self.get_serializer(inventory).data)
        except Exception as exc:
            if hasattr(exc, "messages"):
                return Response({"detail": error_detail(exc)}, status=400)
            raise

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        inventory = self.get_object()
        try:
            inventory.cancel(request.user, request.data.get("reason") or "")
            audit(request.user, "CANCEL", inventory, "Inventário cancelado.")
            return Response(self.get_serializer(inventory).data)
        except Exception as exc:
            if hasattr(exc, "messages"):
                return Response({"detail": error_detail(exc)}, status=400)
            raise
