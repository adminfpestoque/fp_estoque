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

from ..models import Category, Lot, Product, Supplier, SystemSetting, UserProfile
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import (
    CategorySerializer,
    LotSerializer,
    MeSerializer,
    ProductSerializer,
    SupplierSerializer,
    UserSerializer,
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

    @action(detail=False, methods=["get"], permission_classes=[IsInventoryUser])
    def me(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)

    def _set_user_activation(self, request, active):
        user = self.get_object()
        profile = getattr(user, "inventory_profile", None)

        if not active and user.pk == request.user.pk:
            return Response(
                {"detail": "Você não pode inativar o usuário que está usando no momento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_is_admin = bool(
            user.is_superuser or (profile and profile.role == UserProfile.ADMIN)
        )
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

        changed = user.is_active != active or bool(profile and profile.active != active)
        if changed:
            with transaction.atomic():
                user.is_active = active
                user.save(update_fields=["is_active"])
                if profile:
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
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ["name", "description"]
    filterset_fields = ["active"]
    ordering = ["name"]
    ordering_fields = ["name", "created_at"]
    supports_activation = True
    governance_name = "categoria"


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
            entries_count=Count("entries", distinct=True),
            entries_value=Sum("entries__total_value"),
            last_entry=Max("entries__entry_date"),
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

        relations = [
            ("lots", "lots", "Lotes"),
            ("movements", "movements", "Movimentações"),
            ("entry_items", "entries", "Entradas"),
            ("output_items", "outputs", "Saídas"),
            ("adjustments", "adjustments", "Ajustes"),
            ("inventory_items", "inventories", "Inventários"),
        ]
        for relation, code, label in relations:
            manager = getattr(product, relation, None)
            if manager is None:
                continue
            count = manager.count()
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
        blockers = self._deletion_blockers(product)
        if blockers:
            return Response(
                {
                    "detail": (
                        "Este produto possui dados históricos e não pode ser excluído permanentemente. "
                        "Esses registros precisam ser preservados para manter a rastreabilidade do estoque."
                    ),
                    "blockers": blockers,
                    "can_deactivate": product.active,
                },
                status=status.HTTP_409_CONFLICT,
            )

        product_id = product.pk
        metadata = {"product_id": product_id, "code": product.code, "name": product.name}
        try:
            with transaction.atomic():
                audit(
                    request.user,
                    "DELETE",
                    product,
                    "Produto excluído permanentemente.",
                    metadata=metadata,
                )
                product.delete()
        except (ProtectedError, RestrictedError):
            return Response(
                {
                    "detail": (
                        "Este produto possui vínculos protegidos e não pode ser excluído. "
                        "Utilize a ação de inativar."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        refresh_alerts(notify=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        qs = (
            Product.objects.select_related("category", "supplier")
            .prefetch_related("supplier_links__supplier")
            .annotate(lots_count=Count("lots", distinct=True))
        )
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
        qs = self.filter_queryset(self.get_queryset().filter(stock__lte=F("minimum_stock")))
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
        product = self.get_queryset().filter(barcode=value).first()
        if not product:
            raise Http404
        return Response(self.get_serializer(product).data)


class LotViewSet(BaseViewSet):
    queryset = Lot.objects.select_related("product", "supplier").all()
    serializer_class = LotSerializer
    filterset_fields = ["product", "supplier", "active", "expiration_date"]
    search_fields = ["number", "product__name", "product__code", "supplier__name"]
    ordering_fields = ["expiration_date", "quantity", "entry_date", "created_at"]
    http_method_names = ["get", "head", "options"]

    @action(detail=False, methods=["get"])
    def expiring(self, request):
        days = int(
            request.query_params.get("days")
            or SystemSetting.get_int("expiration_alert_days", 30)
        )
        today = timezone.localdate()
        qs = self.filter_queryset(
            self.get_queryset().filter(
                quantity__gt=0,
                expiration_date__gte=today,
                expiration_date__lte=today + timedelta(days=days),
            )
        )
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def expired(self, request):
        qs = self.filter_queryset(
            self.get_queryset().filter(
                quantity__gt=0,
                expiration_date__lt=timezone.localdate(),
            )
        )
        return Response(self.get_serializer(qs, many=True).data)
