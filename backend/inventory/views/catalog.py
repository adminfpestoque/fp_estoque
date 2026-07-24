from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Max, Sum
from django.http import Http404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Category, Lot, Product, Supplier, SystemSetting
from ..permissions import IsAdministrator, IsInventoryUser
from ..serializers import CategorySerializer, LotSerializer, MeSerializer, ProductSerializer, SupplierSerializer, UserSerializer
from ..services import audit, refresh_alerts
from .common import BaseViewSet

User = get_user_model()


class UserViewSet(BaseViewSet):
    queryset = User.objects.select_related("inventory_profile").all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]
    search_fields = ["username", "email", "first_name", "last_name", "inventory_profile__full_name", "inventory_profile__cpf"]
    filterset_fields = ["is_active", "inventory_profile__role", "inventory_profile__active"]
    ordering_fields = ["username", "date_joined", "last_login"]
    ordering = ["username"]

    @action(detail=False, methods=["get"], permission_classes=[IsInventoryUser])
    def me(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        password = request.data.get("password")
        if not password or len(password) < 8:
            return Response({"password": "Informe uma senha com pelo menos 8 caracteres."}, status=400)
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


class SupplierViewSet(BaseViewSet):
    serializer_class = SupplierSerializer
    search_fields = ["name", "corporate_name", "document", "email", "contact_name", "city"]
    filterset_fields = ["active", "state", "city"]
    ordering_fields = ["name", "created_at"]

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

    def perform_create(self, serializer):
        super().perform_create(serializer)
        refresh_alerts(notify=True)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        refresh_alerts(notify=True)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        refresh_alerts(notify=True)

    def get_queryset(self):
        qs = Product.objects.select_related("category", "supplier").prefetch_related("supplier_links__supplier").annotate(lots_count=Count("lots", distinct=True))
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
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(detail=False, methods=["get"])
    def barcode(self, request):
        value = request.query_params.get("value")
        if not value:
            return Response({"detail": "Informe o código de barras."}, status=400)
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
        days = int(request.query_params.get("days") or SystemSetting.get_int("expiration_alert_days", 30))
        today = timezone.localdate()
        qs = self.filter_queryset(self.get_queryset().filter(quantity__gt=0, expiration_date__gte=today, expiration_date__lte=today + timedelta(days=days)))
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def expired(self, request):
        qs = self.filter_queryset(self.get_queryset().filter(quantity__gt=0, expiration_date__lt=timezone.localdate()))
        return Response(self.get_serializer(qs, many=True).data)
