from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from ..models import (Movement, StockAdjustment, StockEntry, StockEntryItem, StockOutput, StockOutputItem)

class StockEntryItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    lot_number_display = serializers.CharField(source="lot.number", read_only=True)

    class Meta:
        model = StockEntryItem
        fields = "__all__"
        read_only_fields = ["entry", "lot", "created_at", "updated_at"]


class StockEntrySerializer(serializers.ModelSerializer):
    items = StockEntryItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.username", read_only=True)

    class Meta:
        model = StockEntry
        fields = "__all__"
        read_only_fields = [
            "number",
            "user",
            "total_value",
            "confirmed_at",
            "cancelled_at",
            "cancelled_by",
            "created_at",
            "updated_at",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        entry = StockEntry.objects.create(user=self.context["request"].user, **validated_data)
        for item in items:
            StockEntryItem.objects.create(entry=entry, **item)
        entry.recalculate_total()
        return entry

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != StockEntry.DRAFT:
            raise serializers.ValidationError("Somente entradas em rascunho podem ser alteradas.")
        items = validated_data.pop("items", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for item in items:
                StockEntryItem.objects.create(entry=instance, **item)
        instance.recalculate_total()
        return instance


class StockOutputItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)

    class Meta:
        model = StockOutputItem
        fields = "__all__"
        read_only_fields = ["output", "created_at", "updated_at"]

    def validate(self, attrs):
        product = attrs.get("product")
        lot = attrs.get("lot")
        if lot and product and lot.product_id != product.id:
            raise serializers.ValidationError({"lot": "O lote não pertence ao produto selecionado."})
        return attrs


class StockOutputSerializer(serializers.ModelSerializer):
    items = StockOutputItemSerializer(many=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.username", read_only=True)

    class Meta:
        model = StockOutput
        fields = "__all__"
        read_only_fields = [
            "number",
            "user",
            "confirmed_at",
            "cancelled_at",
            "cancelled_by",
            "created_at",
            "updated_at",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        output = StockOutput.objects.create(user=self.context["request"].user, **validated_data)
        for item in items:
            StockOutputItem.objects.create(output=output, **item)
        return output

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != StockOutput.DRAFT:
            raise serializers.ValidationError("Somente saídas em rascunho podem ser alteradas.")
        items = validated_data.pop("items", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for item in items:
                StockOutputItem.objects.create(output=instance, **item)
        return instance


class MovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = Movement
        fields = "__all__"
        read_only_fields = [
            "previous_stock",
            "final_stock",
            "user",
            "reversed",
            "reversal_of",
            "entry",
            "output",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        product = attrs.get("product")
        lot = attrs.get("lot")
        if lot and product and lot.product_id != product.id:
            raise serializers.ValidationError({"lot": "O lote não pertence ao produto selecionado."})
        if attrs.get("type") not in {Movement.ENTRY, Movement.OUTPUT, Movement.ADJUSTMENT_IN, Movement.ADJUSTMENT_OUT}:
            raise serializers.ValidationError({"type": "Use entradas, saídas ou ajustes para movimentações manuais."})
        return attrs

    def create(self, validated_data):
        try:
            return Movement.register(user=self.context["request"].user, **validated_data)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise serializers.ValidationError(detail) from exc


class StockAdjustmentSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = StockAdjustment
        fields = "__all__"
        read_only_fields = ["number", "user", "status", "movement", "confirmed_at", "cancelled_at", "created_at", "updated_at"]

    def create(self, validated_data):
        return StockAdjustment.objects.create(user=self.context["request"].user, **validated_data)


