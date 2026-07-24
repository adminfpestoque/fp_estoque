from decimal import Decimal

from rest_framework import serializers

from ..models import Alert, AuditLog, InventoryCount, InventoryItem, Notification, SystemSetting
from .fields import IntegerQuantityField, MoneyField


class InventoryItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)
    system_quantity = IntegerQuantityField(read_only=True)
    counted_quantity = IntegerQuantityField(min_value=0, required=False)
    current_stock = IntegerQuantityField(source="product.stock", read_only=True)
    unit_cost = MoneyField(source="product.cost_price", max_digits=12, read_only=True)
    difference = IntegerQuantityField(read_only=True)
    adjustment_value = MoneyField(max_digits=18, read_only=True)
    counted_by_name = serializers.CharField(source="counted_by.username", read_only=True)

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = [
            "inventory",
            "system_quantity",
            "counted",
            "counted_at",
            "counted_by",
            "adjusted",
            "adjustment_movement",
            "created_at",
            "updated_at",
        ]


class InventorySerializer(serializers.ModelSerializer):
    items = InventoryItemSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.username", read_only=True)
    completed_by_name = serializers.CharField(source="completed_by.username", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    scope_label = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    counted_items = serializers.SerializerMethodField()
    pending_items = serializers.SerializerMethodField()
    divergences_count = serializers.SerializerMethodField()
    positive_divergences = serializers.SerializerMethodField()
    negative_divergences = serializers.SerializerMethodField()
    total_difference = serializers.SerializerMethodField()
    estimated_adjustment_value = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = InventoryCount
        fields = "__all__"
        read_only_fields = [
            "number",
            "user",
            "status",
            "submitted_at",
            "submitted_by",
            "completed_at",
            "completed_by",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]

    def _items(self, obj):
        cache = getattr(obj, "_inventory_items_cache", None)
        if cache is None:
            cache = list(obj.items.select_related("product", "product__category", "counted_by"))
            obj._inventory_items_cache = cache
        return cache

    def get_scope_label(self, obj):
        return obj.category.name if obj.category_id else "Todos os produtos ativos"

    def get_total_items(self, obj):
        return len(self._items(obj))

    def get_counted_items(self, obj):
        return sum(1 for item in self._items(obj) if item.counted)

    def get_pending_items(self, obj):
        return sum(1 for item in self._items(obj) if not item.counted)

    def get_divergences_count(self, obj):
        return sum(1 for item in self._items(obj) if item.counted and item.difference != 0)

    def get_positive_divergences(self, obj):
        return sum(1 for item in self._items(obj) if item.counted and item.difference > 0)

    def get_negative_divergences(self, obj):
        return sum(1 for item in self._items(obj) if item.counted and item.difference < 0)

    def get_total_difference(self, obj):
        return sum(
            (item.difference for item in self._items(obj) if item.counted),
            Decimal("0"),
        )

    def get_estimated_adjustment_value(self, obj):
        return sum(
            (item.adjustment_value for item in self._items(obj) if item.counted),
            Decimal("0"),
        )

    def get_progress_percent(self, obj):
        total = self.get_total_items(obj)
        return round((self.get_counted_items(obj) / total) * 100, 2) if total else 0


class AlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Alert
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "resolved_at"]


class NotificationSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    alert_type = serializers.CharField(source="alert.type", read_only=True, allow_null=True)
    alert_type_display = serializers.CharField(source="alert.get_type_display", read_only=True, allow_null=True)
    alert_active = serializers.BooleanField(source="alert.active", read_only=True, allow_null=True)
    product_name = serializers.CharField(source="alert.product.name", read_only=True, allow_null=True)
    lot_number = serializers.CharField(source="alert.lot.number", read_only=True, allow_null=True)
    inventory_number = serializers.CharField(source="alert.inventory.number", read_only=True, allow_null=True)
    source_display = serializers.SerializerMethodField()
    reference_display = serializers.SerializerMethodField()

    def get_source_display(self, obj):
        return obj.alert.get_type_display() if obj.alert_id else "Evento do sistema"

    def get_reference_display(self, obj):
        if not obj.alert_id:
            return "Sistema"
        if obj.alert.lot_id:
            return f"{obj.alert.product.name} — lote {obj.alert.lot.number}"
        if obj.alert.inventory_id:
            return f"{obj.alert.product.name} — inventário {obj.alert.inventory.number}"
        if obj.alert.product_id:
            return obj.alert.product.name
        return "Alerta de estoque"

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["user", "created_at", "updated_at", "read_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ["created_at"]


class SystemSettingSerializer(serializers.ModelSerializer):
    BOOLEAN_KEYS = {
        "stock_alerts_enabled",
        "expiration_alerts_enabled",
        "inventory_divergence_alerts_enabled",
    }

    class Meta:
        model = SystemSetting
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        key = attrs.get("key", getattr(self.instance, "key", ""))
        value = str(attrs.get("value", getattr(self.instance, "value", ""))).strip()
        if not key:
            raise serializers.ValidationError({"key": "Informe a chave da configuração."})
        if key in self.BOOLEAN_KEYS:
            normalized = value.lower()
            if normalized not in {"true", "false", "1", "0", "sim", "não", "nao"}:
                raise serializers.ValidationError({"value": "Use verdadeiro ou falso para esta configuração."})
            attrs["value"] = "true" if normalized in {"true", "1", "sim"} else "false"
        elif key == "expiration_alert_days":
            try:
                days = int(value)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError({"value": "Informe uma quantidade inteira de dias."}) from exc
            if not 1 <= days <= 365:
                raise serializers.ValidationError({"value": "Informe um valor entre 1 e 365 dias."})
            attrs["value"] = str(days)
        elif not value:
            raise serializers.ValidationError({"value": "Informe um valor."})
        return attrs
