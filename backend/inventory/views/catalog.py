from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.deletion import ProtectedError, RestrictedError
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Category, Lot, PackagingType, Product, Supplier, SystemSetting, UserProfile
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import (
    CategorySerializer,
    LotSerializer,
    MeSerializer,
    PackagingTypeSerializer,
    ProductSerializer,
    SupplierSerializer,
    UserSerializer,
    UserProfileSerializer,
)
from ..services import audit, refresh_alerts
from .common import BaseViewSet

User = get_user_model()


class UserViewSet(BaseViewSet):
    queryset = User.objects.select_related("inventory_profile").all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]
    search_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "inventory_profile__full_name",
        "inventory_profile__cpf",
    ]
    filterset_fields = ["is_active", "inventory_profile__role", "inventory_profile__active"]
    ordering_fields = ["username", "date_joined", "last_login"]
    ordering = ["username"]
    governance_name = "usuário"

    @action(detail=False, methods=["get", "patch"], permission_classes=[IsInventoryUser])
    def me(self, request):
        if request.method == "PATCH":
            allowed = {"theme", "font_scale", "reduced_motion", "enhanced_focus"}
            unknown = set(request.data) - allowed
            if unknown:
                return Response(
                    {"detail": "Apenas preferências de aparência e acessibilidade podem ser alteradas aqui."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={"full_name": request.user.get_full_name() or request.user.username},
            )
            serializer = UserProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(
                request.user,
                "UPDATE_ACCESSIBILITY",
                request.user,
                "Preferências de aparência e acessibilidade atualizadas.",
                metadata={key: serializer.validated_data.get(key) for key in allowed if key in serializer.validated_data},
            )
            request.user.refresh_from_db()
        return Response(MeSerializer(request.user, context={"request": request}).data)

    def _set_user_activation(self, request, active):
        user = self.get_object()
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"full_name": user.get_full_name() or user.username},
        )

        if not active and user.pk == request.user.pk:
            return Response(
                {"detail": "Você não pode inativar o usuário que está usando no momento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_is_admin = bool(user.is_superuser or profile.role == UserProfile.ADMIN)
        if not active and target_is_admin:
            has_other_admin = (
                User.objects.filter(is_active=True)
                .filter(
                    Q(is_superuser=True)
                    | Q(
                        inventory_profile__role=UserProfile.ADMIN,
                        inventory_profile__active=True,
                    )
                )
                .exclude(pk=user.pk)
                .exists()
            )
            if not has_other_admin:
                return Response(
                    {"detail": "Não é possível inativar o último administrador ativo do sistema."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if user.is_active != active or profile.active != active:
            with transaction.atomic():
                user.is_active = active
                user.save(update_fields=["is_active"])
                profile.active = active
                profile.save(update_fields=["active", "updated_at"])
                audit(
                    request.user,
                    "ACTIVATE" if active else "DEACTIVATE",
                    user,
                    f"Status do usuário alterado para {'ativo' if active else 'inativo'}.",
                )

        user = self.get_queryset().get(pk=user.pk)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        return self._set_user_activation(request, True)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return self._set_user_activation(request, False)

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        password = request.data.get("password")
        if not password or len(password) < 8:
            return Response(
                {"password": "Informe uma senha com pelo menos 8 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(password)
        user.save(update_fields=["password"])
        audit(request.user, "RESET_PASSWORD", user, "Senha redefinida por administrador.")
        return Response({"detail": "Senha redefinida com sucesso."})


class CategoryViewSet(BaseViewSet):
    queryset = Category.objects.prefetch_related("packaging_types").all()
    serializer_class = CategorySerializer
    search_fields = ["name", "description"]
    filterset_fields = ["active"]
    ordering = ["name"]
    ordering_fields = ["name", "created_at"]
    supports_activation = True
    governance_name = "categoria"


class PackagingTypeViewSet(BaseViewSet):
    serializer_class = PackagingTypeSerializer
    search_fields = ["name"]
    filterset_fields = ["active"]
    ordering = ["name"]
    ordering_fields = ["name", "created_at"]
    supports_activation = True
    governance_name = "tipo de embalagem"

    def get_queryset(self):
        return PackagingType.objects.annotate(
            products_count=Count("product_options", distinct=True),
            categories_count=Count("categories", distinct=True),
        ).order_by("name")

    def destroy(self, request, *args, **kwargs):
        packaging_type = self.get_object()
        product_count = packaging_type.product_options.count()
        category_count = packaging_type.categories.count()
        if product_count or category_count:
            return Response(
                {
                    "detail": (
                        "Este tipo de embalagem está sendo usado por produtos ou categorias. "
                        "Remova os vínculos ou inative o tipo para preservar o histórico."
                    ),
                    "products_count": product_count,
                    "categories_count": category_count,
                    "can_deactivate": packaging_type.active,
                },
                status=status.HTTP_409_CONFLICT,
            )
        name = packaging_type.name
        packaging_type.delete()
        audit(request.user, "DELETE", None, f'Tipo de embalagem "{name}" excluído.')
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupplierViewSet(BaseViewSet):
    serializer_class = SupplierSerializer
    search_fields = ["name", "corporate_name", "document", "email", "contact_name", "city"]
    filterset_fields = ["active", "state", "city"]
    ordering_fields = ["name", "created_at"]
    supports_activation = True
    governance_name = "fornecedor"

    def get_queryset(self):
        return Supplier.objects.annotate(
            products_count=Count("product_links", distinct=True),
            entries_count=Count("entries", filter=Q(entries__deleted_at__isnull=True), distinct=True),
            entries_value=Sum("entries__total_value", filter=Q(entries__deleted_at__isnull=True)),
            last_entry=Max("entries__entry_date", filter=Q(entries__deleted_at__isnull=True)),
        ).order_by("name")


class ProductViewSet(BaseViewSet):
    serializer_class = ProductSerializer
    filterset_fields = ["category", "supplier", "active", "brand"]
    search_fields = ["name", "code", "sku", "barcode", "brand", "description", "location"]
    ordering_fields = ["name", "stock", "minimum_stock", "cost_price", "sale_price", "created_at"]
    supports_activation = True
    governance_name = "produto"

    def perform_create(self, serializer):
        super().perform_create(serializer)
        refresh_alerts(notify=True)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        refresh_alerts(notify=True)

    def after_activation_change(self, instance, active):
        refresh_alerts(notify=True)

    def _set_activation(self, request, active):
        product = self.get_object()
        if product.is_deleted:
            return Response(
                {
                    "detail": (
                        "Este produto foi excluído e permanece disponível somente para histórico. "
                        "Não é possível ativá-lo, inativá-lo ou editá-lo."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super()._set_activation(request, active)

    @staticmethod
    def _deletion_blockers(product):
        blockers = []
        if product.stock > 0:
            blockers.append(
                {
                    "code": "stock",
                    "label": "Estoque atual",
                    "count": int(product.stock),
                    "description": f"{int(product.stock)} unidade(s) em estoque",
                }
            )

        live_lots = product.lots.filter(quantity__gt=0).count()
        if live_lots:
            blockers.append(
                {
                    "code": "lots",
                    "label": "Lotes com saldo",
                    "count": live_lots,
                    "description": f"{live_lots} lote(s) ainda possuem saldo",
                }
            )

        active_entries = product.entry_items.filter(entry__deleted_at__isnull=True).count()
        if active_entries:
            blockers.append(
                {
                    "code": "entries",
                    "label": "Entradas não excluídas",
                    "count": active_entries,
                    "description": f"{active_entries} item(ns) em entradas não excluídas",
                }
            )

        active_outputs = product.output_items.filter(output__deleted_at__isnull=True).count()
        if active_outputs:
            blockers.append(
                {
                    "code": "outputs",
                    "label": "Saídas não excluídas",
                    "count": active_outputs,
                    "description": f"{active_outputs} item(ns) em saídas não excluídas",
                }
            )

        deleted_document_movements = (
            Q(entry__deleted_at__isnull=False)
            | Q(output__deleted_at__isnull=False)
            | Q(reversal_of__entry__deleted_at__isnull=False)
            | Q(reversal_of__output__deleted_at__isnull=False)
        )
        active_movements = product.movements.exclude(deleted_document_movements).count()
        if active_movements:
            blockers.append(
                {
                    "code": "movements",
                    "label": "Movimentações preservadas",
                    "count": active_movements,
                    "description": f"{active_movements} movimentação(ões) não pertencem a documentos excluídos",
                }
            )

        governance_relations = [
            ("adjustments", "adjustments", "Ajustes"),
            ("inventory_items", "inventories", "Inventários"),
        ]
        for relation, code, label in governance_relations:
            count = getattr(product, relation).count()
            if count:
                blockers.append(
                    {
                        "code": code,
                        "label": label,
                        "count": count,
                        "description": f"{count} registro(s) em {label.lower()}",
                    }
                )
        return blockers

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        if product.is_deleted:
            return Response(self.get_serializer(product).data)

        blockers = self._deletion_blockers(product)
        if blockers:
            return Response(
                {
                    "detail": (
                        "Este produto ainda possui estoque ou vínculos operacionais e não pode ser excluído. "
                        "Exclua ou regularize os registros relacionados antes de continuar."
                    ),
                    "blockers": blockers,
                    "can_deactivate": product.active,
                },
                status=status.HTTP_409_CONFLICT,
            )

        metadata = {"product_id": product.pk, "code": product.code, "name": product.name}
        with transaction.atomic():
            product.active = False
            product.deleted_at = timezone.now()
            product.deleted_by = request.user
            product.deletion_reason = str(request.data.get("reason") or "").strip()
            product.save(
                update_fields=[
                    "active",
                    "deleted_at",
                    "deleted_by",
                    "deletion_reason",
                    "updated_at",
                ]
            )
            audit(
                request.user,
                "DELETE",
                product,
                "Produto excluído do uso operacional e mantido no histórico.",
                metadata=metadata,
            )

        refresh_alerts(notify=True)
        return Response(self.get_serializer(product).data)

    def get_queryset(self):
        qs = (
            Product.objects.select_related("category", "supplier")
            .prefetch_related("supplier_links__supplier", "packaging_options__packaging_type")
            .annotate(lots_count=Count("lots", distinct=True))
        )
        deleted = str(self.request.query_params.get("deleted") or "").lower()
        detail_actions = {
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "activate",
            "deactivate",
        }
        if deleted == "true":
            qs = qs.filter(deleted_at__isnull=False)
        elif deleted != "all" and getattr(self, "action", None) not in detail_actions:
            qs = qs.filter(deleted_at__isnull=True)

        level = self.request.query_params.get("stock_level")
        if level == "low":
            qs = qs.filter(stock__lte=F("minimum_stock"), stock__gt=0)
        elif level == "out":
            qs = qs.filter(stock=0)
        elif level == "normal":
            qs = qs.filter(stock__gt=F("minimum_stock"))
        return qs

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        qs = self.filter_queryset(
            self.get_queryset().filter(
                active=True, deleted_at__isnull=True, stock__lte=F("minimum_stock")
            )
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        return (
            self.get_paginated_response(serializer.data)
            if page is not None
            else Response(serializer.data)
        )

    @action(detail=False, methods=["get"])
    def barcode(self, request):
        value = request.query_params.get("value")
        if not value:
            return Response(
                {"detail": "Informe o código de barras."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = self.get_queryset().filter(
            barcode=value, active=True, deleted_at__isnull=True
        ).first()
        if not product:
            raise Http404
        return Response(self.get_serializer(product).data)



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
