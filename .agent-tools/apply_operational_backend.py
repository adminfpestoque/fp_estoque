from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado em {path}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def replace_from(path, marker, replacement):
    text = read(path)
    index = text.index(marker)
    write(path, text[:index] + replacement.rstrip() + "\n")


# Lotes operacionais: somente produtos ainda cadastrados e filtros de saldo.
replace_from(
    "backend/inventory/views/catalog.py",
    "class LotViewSet(BaseViewSet):",
    dedent('''
    class LotViewSet(BaseViewSet):
        queryset = Lot.objects.select_related("product", "product__category", "supplier").all()
        serializer_class = LotSerializer
        filterset_fields = ["product", "supplier", "active", "expiration_date"]
        search_fields = [
            "number",
            "product__name",
            "product__code",
            "product_name_snapshot",
            "product_code_snapshot",
            "supplier__name",
        ]
        ordering_fields = ["expiration_date", "quantity", "entry_date", "created_at"]
        http_method_names = ["get", "head", "options"]

        def get_queryset(self):
            queryset = super().get_queryset()
            include_history = str(
                self.request.query_params.get("history") or "false"
            ).lower() in {"true", "1", "yes"}
            if not include_history:
                queryset = queryset.filter(
                    product__isnull=False,
                    product__deleted_at__isnull=True,
                )

            balance = str(self.request.query_params.get("balance") or "").lower()
            if balance in {"positive", "available", "with_stock"}:
                queryset = queryset.filter(quantity__gt=0)
            elif balance in {"empty", "zero"}:
                queryset = queryset.filter(quantity=0)

            view = str(self.request.query_params.get("view") or "").lower()
            today = timezone.localdate()
            if view == "available":
                queryset = queryset.filter(quantity__gt=0)
            elif view == "expiring":
                days = int(
                    self.request.query_params.get("days")
                    or SystemSetting.get_int("expiration_alert_days", 30)
                )
                queryset = queryset.filter(
                    quantity__gt=0,
                    expiration_date__gte=today,
                    expiration_date__lte=today + timedelta(days=days),
                )
            elif view == "expired":
                queryset = queryset.filter(
                    quantity__gt=0,
                    expiration_date__lt=today,
                )
            elif view == "empty":
                queryset = queryset.filter(quantity=0)

            return queryset

        @action(detail=False, methods=["get"])
        def expiring(self, request):
            days = int(
                request.query_params.get("days")
                or SystemSetting.get_int("expiration_alert_days", 30)
            )
            today = timezone.localdate()
            queryset = self.filter_queryset(
                self.get_queryset().filter(
                    quantity__gt=0,
                    expiration_date__gte=today,
                    expiration_date__lte=today + timedelta(days=days),
                )
            )
            return Response(self.get_serializer(queryset, many=True).data)

        @action(detail=False, methods=["get"])
        def expired(self, request):
            queryset = self.filter_queryset(
                self.get_queryset().filter(
                    quantity__gt=0,
                    expiration_date__lt=timezone.localdate(),
                )
            )
            return Response(self.get_serializer(queryset, many=True).data)
    ''')
)

replace_once(
    "backend/inventory/serializers/catalog.py",
    '    supplier_name = serializers.CharField(source="supplier.name", read_only=True)\n    status = serializers.CharField(read_only=True)',
    '    supplier_name = serializers.CharField(source="supplier.name", read_only=True)\n    product_active = serializers.BooleanField(source="product.active", read_only=True, allow_null=True)\n    product_status = serializers.CharField(source="product.display_status", read_only=True, allow_null=True)\n    status = serializers.CharField(read_only=True)',
)

# Inventários abrangem produtos existentes, inclusive inativos, mas nunca excluídos.
replace_once(
    "backend/inventory/views/inventories.py",
    '        products = Product.objects.filter(active=True).select_related("category")',
    '        products = Product.objects.filter(deleted_at__isnull=True).select_related("category")',
)
replace_once(
    "backend/inventory/views/inventories.py",
    '        product = Product.objects.filter(pk=payload.get("product"), active=True).first()\n        if not product:\n            raise DRFValidationError({"product": "Produto não encontrado ou inativo."})',
    '        product = Product.objects.filter(\n            pk=payload.get("product"), deleted_at__isnull=True\n        ).first()\n        if not product:\n            raise DRFValidationError({"product": "Produto não encontrado ou excluído."})',
)
replace_once(
    "backend/inventory/serializers/misc.py",
    '        return obj.category.name if obj.category_id else "Todos os produtos ativos"',
    '        return obj.category.name if obj.category_id else "Todos os produtos cadastrados"',
)

# Ajustes: validação, atomicidade e rastreabilidade completas.
write(
    "backend/inventory/models/adjustment.py",
    dedent('''
    from django.conf import settings
    from django.core.exceptions import ValidationError
    from django.db import models, transaction
    from django.db.models import Q
    from django.utils import timezone

    from .base import NumberedDocument
    from .catalog import Lot, Product
    from .movement import Movement


    class StockAdjustment(NumberedDocument):
        POSITIVE = "POSITIVE"
        NEGATIVE = "NEGATIVE"
        TYPES = [(POSITIVE, "Positivo"), (NEGATIVE, "Negativo")]
        DRAFT = "DRAFT"
        CONFIRMED = "CONFIRMED"
        CANCELLED = "CANCELLED"
        STATUSES = [(DRAFT, "Rascunho"), (CONFIRMED, "Confirmado"), (CANCELLED, "Cancelado")]

        product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="adjustments")
        lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustments")
        type = models.CharField(max_length=10, choices=TYPES)
        quantity = models.DecimalField(max_digits=14, decimal_places=3)
        reason = models.CharField(max_length=200)
        justification = models.TextField()
        user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_adjustments")
        status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
        confirmed_at = models.DateTimeField(null=True, blank=True)
        cancelled_at = models.DateTimeField(null=True, blank=True)
        movement = models.OneToOneField(Movement, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustment")

        class Meta:
            ordering = ["-created_at"]
            constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="inv_adjustment_qty_valid")]

        def save(self, *args, **kwargs):
            self.ensure_number("AJU")
            super().save(*args, **kwargs)

        def _validate_links(self):
            if self.product.deleted_at is not None:
                raise ValidationError("Um produto excluído não pode receber novos ajustes.")
            if self.lot_id and self.lot.product_id != self.product_id:
                raise ValidationError("O lote não pertence ao produto selecionado.")

        @transaction.atomic
        def confirm(self, user=None):
            if self.status != self.DRAFT:
                raise ValidationError("Somente ajustes em rascunho podem ser confirmados.")

            product = Product.objects.select_for_update().get(pk=self.product_id)
            lot = None
            if self.lot_id:
                lot = Lot.objects.select_for_update().get(pk=self.lot_id)
            self.product = product
            self.lot = lot
            self._validate_links()

            movement = Movement.register(
                product=product,
                lot=lot,
                type=Movement.ADJUSTMENT_IN if self.type == self.POSITIVE else Movement.ADJUSTMENT_OUT,
                quantity=self.quantity,
                user=user or self.user,
                reason=self.reason,
                notes=self.justification,
                document=self.number,
            )
            self.movement = movement
            self.status = self.CONFIRMED
            self.confirmed_at = timezone.now()
            self.cancelled_at = None
            self.save(
                update_fields=[
                    "movement",
                    "status",
                    "confirmed_at",
                    "cancelled_at",
                    "updated_at",
                ]
            )
            return self

        @transaction.atomic
        def cancel(self, user):
            if self.status != self.CONFIRMED or not self.movement:
                raise ValidationError("Somente ajustes confirmados podem ser cancelados.")
            Movement.reverse(
                original=self.movement,
                user=user,
                reason=f"Cancelamento do ajuste {self.number}",
            )
            self.status = self.CANCELLED
            self.cancelled_at = timezone.now()
            self.save(update_fields=["status", "cancelled_at", "updated_at"])
            return self
    ''')
)

replace_once(
    "backend/inventory/serializers/documents.py",
    '    Movement,\n    Product,',
    '    Lot,\n    Movement,\n    Product,',
)
replace_from(
    "backend/inventory/serializers/documents.py",
    "class StockAdjustmentSerializer(serializers.ModelSerializer):",
    dedent('''
    class StockAdjustmentSerializer(serializers.ModelSerializer):
        product = serializers.PrimaryKeyRelatedField(
            queryset=Product.objects.filter(deleted_at__isnull=True)
        )
        lot = serializers.PrimaryKeyRelatedField(
            queryset=Lot.objects.filter(product__deleted_at__isnull=True),
            required=False,
            allow_null=True,
        )
        quantity = IntegerQuantityField(min_value=1)
        product_name = serializers.CharField(source="product.name", read_only=True)
        product_code = serializers.CharField(source="product.code", read_only=True)
        category_name = serializers.CharField(source="product.category.name", read_only=True)
        product_active = serializers.BooleanField(source="product.active", read_only=True)
        product_stock = IntegerQuantityField(source="product.stock", read_only=True)
        lot_number = serializers.CharField(source="lot.number", read_only=True, allow_null=True)
        lot_quantity = IntegerQuantityField(source="lot.quantity", read_only=True, allow_null=True)
        user_name = serializers.CharField(source="user.username", read_only=True)
        type_display = serializers.CharField(source="get_type_display", read_only=True)
        status_display = serializers.CharField(source="get_status_display", read_only=True)
        movement_previous_stock = IntegerQuantityField(
            source="movement.previous_stock", read_only=True, allow_null=True
        )
        movement_final_stock = IntegerQuantityField(
            source="movement.final_stock", read_only=True, allow_null=True
        )
        movement_reversed = serializers.BooleanField(
            source="movement.reversed", read_only=True, allow_null=True
        )

        class Meta:
            model = StockAdjustment
            fields = "__all__"
            read_only_fields = [
                "number",
                "user",
                "status",
                "movement",
                "confirmed_at",
                "cancelled_at",
                "created_at",
                "updated_at",
            ]

        def validate(self, attrs):
            instance = self.instance
            product = attrs.get("product", getattr(instance, "product", None))
            lot = attrs.get("lot", getattr(instance, "lot", None))
            adjustment_type = attrs.get("type", getattr(instance, "type", None))
            quantity = attrs.get("quantity", getattr(instance, "quantity", None))

            if not product or product.deleted_at is not None:
                raise serializers.ValidationError(
                    {"product": "Selecione um produto que permaneça cadastrado."}
                )
            if lot and lot.product_id != product.id:
                raise serializers.ValidationError(
                    {"lot": "O lote não pertence ao produto selecionado."}
                )
            if adjustment_type == StockAdjustment.NEGATIVE and quantity:
                if quantity > product.stock:
                    raise serializers.ValidationError(
                        {"quantity": "A quantidade é maior que o estoque atual do produto."}
                    )
                if lot and quantity > lot.quantity:
                    raise serializers.ValidationError(
                        {"quantity": "A quantidade é maior que o saldo disponível no lote."}
                    )

            if "reason" in attrs:
                attrs["reason"] = attrs["reason"].strip()
            if "justification" in attrs:
                attrs["justification"] = attrs["justification"].strip()
            return attrs

        def create(self, validated_data):
            return StockAdjustment.objects.create(
                user=self.context["request"].user,
                **validated_data,
            )

        def update(self, instance, validated_data):
            if instance.status != StockAdjustment.DRAFT:
                raise serializers.ValidationError(
                    "Somente ajustes em rascunho podem ser alterados."
                )
            return super().update(instance, validated_data)
    ''')
)

replace_once(
    "backend/inventory/views/documents.py",
    "from django.core.exceptions import ValidationError as DjangoValidationError\n",
    "from django.core.exceptions import ValidationError as DjangoValidationError\nfrom django.db.models import Count, Q, Sum\n",
)
replace_from(
    "backend/inventory/views/documents.py",
    "class StockAdjustmentViewSet(BaseViewSet):",
    dedent('''
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
    ''')
)

write(
    "backend/inventory/test_operational_consistency.py",
    dedent('''
    from decimal import Decimal

    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from django.utils import timezone
    from rest_framework.test import APIClient

    from .models import Category, InventoryCount, Lot, Product, StockAdjustment, UserProfile


    User = get_user_model()


    class OperationalConsistencyTests(TestCase):
        def setUp(self):
            self.admin = User.objects.create_user(
                "operational-admin",
                password="OperationalAdmin123!",
                is_staff=True,
                is_superuser=True,
            )
            UserProfile.objects.create(
                user=self.admin,
                full_name="Administrador operacional",
                role=UserProfile.ADMIN,
            )
            self.category = Category.objects.create(name="Refrigerantes operacionais")
            self.active_product = Product.objects.create(
                code="OP-ACTIVE",
                name="Produto ativo",
                category=self.category,
                stock=Decimal("10"),
                cost_price=Decimal("5"),
            )
            self.inactive_product = Product.objects.create(
                code="OP-INACTIVE",
                name="Produto inativo existente",
                category=self.category,
                stock=Decimal("4"),
                cost_price=Decimal("3"),
                active=False,
            )
            self.deleted_product = Product.objects.create(
                code="OP-DELETED",
                name="Produto excluído histórico",
                category=self.category,
                stock=Decimal("0"),
                active=False,
                deleted_at=timezone.now(),
                deleted_by=self.admin,
            )
            self.active_lot = Lot.objects.create(
                product=self.active_product,
                number="LOT-ACTIVE",
                received_quantity=Decimal("10"),
                quantity=Decimal("10"),
            )
            self.empty_lot = Lot.objects.create(
                product=self.inactive_product,
                number="LOT-EMPTY",
                received_quantity=Decimal("4"),
                quantity=Decimal("0"),
            )
            self.deleted_lot = Lot.objects.create(
                product=self.deleted_product,
                number="LOT-DELETED",
                received_quantity=Decimal("1"),
                quantity=Decimal("0"),
            )
            self.client = APIClient()
            self.client.force_authenticate(self.admin)

        @staticmethod
        def rows(response):
            return response.data.get("results", response.data)

        def test_lot_screen_hides_deleted_products_and_defaults_can_show_balance_only(self):
            response = self.client.get("/api/lots/", {"view": "available", "page_size": 100})
            self.assertEqual(response.status_code, 200, response.data)
            numbers = {row["number"] for row in self.rows(response)}
            self.assertEqual(numbers, {"LOT-ACTIVE"})

            all_existing = self.client.get("/api/lots/", {"view": "all", "page_size": 100})
            self.assertEqual(all_existing.status_code, 200, all_existing.data)
            numbers = {row["number"] for row in self.rows(all_existing)}
            self.assertEqual(numbers, {"LOT-ACTIVE", "LOT-EMPTY"})
            self.assertNotIn("LOT-DELETED", numbers)

        def test_inventory_includes_active_and_inactive_existing_products(self):
            response = self.client.post(
                "/api/inventories/",
                {"category": self.category.id, "notes": "Conferência", "populate": True},
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["status"], InventoryCount.OPEN)
            ids = {item["product"] for item in response.data["items"]}
            self.assertEqual(ids, {self.active_product.id, self.inactive_product.id})
            self.assertNotIn(self.deleted_product.id, ids)

        def test_adjustment_draft_confirmation_summary_and_cancellation(self):
            create = self.client.post(
                "/api/adjustments/",
                {
                    "product": self.inactive_product.id,
                    "type": StockAdjustment.POSITIVE,
                    "quantity": 2,
                    "reason": "Correção de contagem",
                    "justification": "Duas unidades foram localizadas na conferência física.",
                },
                format="json",
            )
            self.assertEqual(create.status_code, 201, create.data)
            self.assertEqual(create.data["status"], StockAdjustment.DRAFT)

            confirm = self.client.post(f"/api/adjustments/{create.data['id']}/confirm/")
            self.assertEqual(confirm.status_code, 200, confirm.data)
            self.assertEqual(confirm.data["status"], StockAdjustment.CONFIRMED)
            self.assertEqual(Decimal(str(confirm.data["movement_previous_stock"])), Decimal("4"))
            self.assertEqual(Decimal(str(confirm.data["movement_final_stock"])), Decimal("6"))

            summary = self.client.get("/api/adjustments/summary/")
            self.assertEqual(summary.status_code, 200, summary.data)
            self.assertEqual(summary.data["confirmed"], 1)
            self.assertEqual(Decimal(str(summary.data["positive_quantity"])), Decimal("2"))

            cancel = self.client.post(f"/api/adjustments/{create.data['id']}/cancel/")
            self.assertEqual(cancel.status_code, 200, cancel.data)
            self.assertEqual(cancel.data["status"], StockAdjustment.CANCELLED)
            self.assertTrue(cancel.data["movement_reversed"])
            self.inactive_product.refresh_from_db()
            self.assertEqual(self.inactive_product.stock, Decimal("4"))

        def test_deleted_product_cannot_receive_adjustment(self):
            response = self.client.post(
                "/api/adjustments/",
                {
                    "product": self.deleted_product.id,
                    "type": StockAdjustment.POSITIVE,
                    "quantity": 1,
                    "reason": "Correção",
                    "justification": "Não deve ser permitido.",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("product", response.data)
    ''')
)
