from decimal import Decimal

from rest_framework import serializers

from ..models import Alert, AuditLog, InventoryCount, InventoryItem, Notification, SystemSetting


class InventoryItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)
    current_stock = serializers.DecimalField(
        source="product.stock",
        max_digits=14,
        decimal_places=3,
        read_only=True,
    )
    unit_cost = serializers.DecimalField(
        source="product.cost_price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    difference = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    adjustment_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
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
    class Meta:
        model = SystemSetting
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
