from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from ..models import (
    Lot,
    Movement,
    Product,
    ProductPackaging,
    StockAdjustment,
    StockEntry,
    StockEntryItem,
    StockOutput,
    StockOutputItem,
)
from .fields import IntegerQuantityField, MoneyField


def validation_detail(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return getattr(exc, "messages", [str(exc)])


class StockEntryItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=True,
        allow_null=False,
    )
    packaging = serializers.PrimaryKeyRelatedField(
        queryset=ProductPackaging.objects.all(),
        required=False,
        allow_null=True,
    )
    entry_quantity = IntegerQuantityField(min_value=1, required=False)
    purchase_price = MoneyField(max_digits=12, min_value=0, required=False)
    quantity = IntegerQuantityField(read_only=True)
    unit_cost = MoneyField(max_digits=12, read_only=True)
    product_name = serializers.CharField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    subtotal = MoneyField(max_digits=16, read_only=True)
    lot_number_display = serializers.CharField(source="lot.number", read_only=True)
    entry_unit_description = serializers.CharField(read_only=True)

    class Meta:
        model = StockEntryItem
        fields = "__all__"
        read_only_fields = [
            "entry",
            "lot",
            "product_name_snapshot",
            "product_code_snapshot",
            "entry_unit_name",
            "conversion_factor",
            "quantity",
            "unit_cost",
            "created_at",
            "updated_at",
        ]

    def to_internal_value(self, data):
        # Compatibilidade com integrações antigas que enviavam quantidade e custo por unidade.
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        if mutable.get("entry_quantity") in (None, "") and mutable.get("quantity") not in (None, ""):
            mutable["entry_quantity"] = mutable.get("quantity")
        if mutable.get("purchase_price") in (None, "") and mutable.get("unit_cost") not in (None, ""):
            mutable["purchase_price"] = mutable.get("unit_cost")
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        product = attrs.get("product")
        packaging = attrs.get("packaging")
        entry_quantity = attrs.get("entry_quantity") or 1
        purchase_price = attrs.get("purchase_price")

        if not product or product.deleted_at or not product.active:
            raise serializers.ValidationError(
                {"product": "Selecione um produto ativo e disponível para entrada."}
            )
        if packaging:
            if packaging.product_id != product.id:
                raise serializers.ValidationError(
                    {"packaging": "A forma de entrada não pertence ao produto selecionado."}
                )
            if not packaging.active:
                raise serializers.ValidationError(
                    {"packaging": "A forma de entrada selecionada está inativa."}
                )
            attrs["entry_unit_name"] = packaging.display_name
            attrs["conversion_factor"] = packaging.units_per_package
            if purchase_price is None:
                purchase_price = packaging.cost_price
        else:
            attrs["entry_unit_name"] = "Unidade"
            attrs["conversion_factor"] = 1
            if purchase_price is None:
                purchase_price = product.cost_price

        attrs["entry_quantity"] = entry_quantity
        attrs["purchase_price"] = purchase_price
        attrs["quantity"] = entry_quantity * attrs["conversion_factor"]
        attrs["unit_cost"] = purchase_price / attrs["conversion_factor"]
        return attrs


class StockEntrySerializer(serializers.ModelSerializer):
    items = StockEntryItemSerializer(many=True)
    total_value = MoneyField(max_digits=14, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.username", read_only=True)
    deleted_by_name = serializers.CharField(source="deleted_by.username", read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    display_status = serializers.CharField(read_only=True)

    class Meta:
        model = StockEntry
        fields = "__all__"
        read_only_fields = [
            "number",
            "user",
            "status",
            "total_value",
            "confirmed_at",
            "cancelled_at",
            "cancelled_by",
            "deleted_at",
            "deleted_by",
            "deletion_reason",
            "created_at",
            "updated_at",
        ]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Inclua ao menos um produto.")
        return items

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
        if instance.is_deleted:
            raise serializers.ValidationError("Uma entrada excluída não pode ser alterada.")

        request_user = self.context["request"].user
        items = validated_data.pop("items", None)
        was_confirmed = instance.status == StockEntry.CONFIRMED

        try:
            if was_confirmed:
                instance.cancel(request_user)
                instance.refresh_from_db()
                instance.status = StockEntry.DRAFT
                instance.confirmed_at = None
                instance.cancelled_at = None
                instance.cancelled_by = None
                instance.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "cancelled_at",
                        "cancelled_by",
                        "updated_at",
                    ]
                )

            for key, value in validated_data.items():
                setattr(instance, key, value)
            instance.save()

            if items is not None:
                instance.items.all().delete()
                for item in items:
                    StockEntryItem.objects.create(entry=instance, **item)

            if not instance.items.exists():
                raise serializers.ValidationError({"items": "Inclua ao menos um produto."})

            instance.recalculate_total()
            if was_confirmed:
                instance.confirm(request_user)
            instance.refresh_from_db()
            return instance
        except DjangoValidationError as exc:
            raise serializers.ValidationError(validation_detail(exc)) from exc


class StockOutputItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=True,
        allow_null=False,
    )
    packaging = serializers.PrimaryKeyRelatedField(
        queryset=ProductPackaging.objects.all(),
        required=False,
        allow_null=True,
    )
    sale_quantity = IntegerQuantityField(min_value=1, required=False)
    quantity = IntegerQuantityField(read_only=True)
    unit_sale_price = MoneyField(max_digits=12, read_only=True)
    sale_price = MoneyField(max_digits=12, read_only=True)
    subtotal = MoneyField(max_digits=16, read_only=True)
    product_name = serializers.CharField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)
    sale_unit_description = serializers.CharField(read_only=True)

    class Meta:
        model = StockOutputItem
        fields = "__all__"
        read_only_fields = [
            "output",
            "product_name_snapshot",
            "product_code_snapshot",
            "sale_unit_name",
            "conversion_factor",
            "quantity",
            "unit_sale_price",
            "sale_price",
            "created_at",
            "updated_at",
        ]

    def to_internal_value(self, data):
        # Compatibilidade com integrações antigas que enviavam apenas quantity.
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        if mutable.get("sale_quantity") in (None, "") and mutable.get("quantity") not in (None, ""):
            mutable["sale_quantity"] = mutable.get("quantity")
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        product = attrs.get("product")
        packaging = attrs.get("packaging")
        lot = attrs.get("lot")
        sale_quantity = attrs.get("sale_quantity") or 1

        if not product or product.deleted_at or not product.active:
            raise serializers.ValidationError(
                {"product": "Selecione um produto ativo e disponível para venda."}
            )
        if packaging:
            if packaging.product_id != product.id:
                raise serializers.ValidationError(
                    {"packaging": "A forma de saída não pertence ao produto selecionado."}
                )
            if not packaging.active:
                raise serializers.ValidationError(
                    {"packaging": "A forma de saída selecionada está inativa."}
                )
            attrs["sale_unit_name"] = packaging.display_name
            attrs["conversion_factor"] = packaging.units_per_package
            attrs["sale_price"] = packaging.sale_price
        else:
            attrs["sale_unit_name"] = "Unidade"
            attrs["conversion_factor"] = 1
            attrs["sale_price"] = product.sale_price

        attrs["sale_quantity"] = sale_quantity
        attrs["quantity"] = sale_quantity * attrs["conversion_factor"]
        attrs["unit_sale_price"] = attrs["sale_price"] / attrs["conversion_factor"]

        if lot:
            if lot.product_id != product.id:
                raise serializers.ValidationError(
                    {"lot": "O lote não pertence ao produto selecionado."}
                )
            if not lot.active or lot.quantity <= 0:
                raise serializers.ValidationError(
                    {"lot": "O lote selecionado não possui saldo disponível."}
                )
        return attrs


class StockOutputSerializer(serializers.ModelSerializer):
    items = StockOutputItemSerializer(many=True)
    total_value = MoneyField(max_digits=14, read_only=True)
    amount_received = MoneyField(max_digits=14, min_value=0, required=False)
    change_amount = MoneyField(max_digits=14, read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    cancelled_by_name = serializers.CharField(source="cancelled_by.username", read_only=True)
    deleted_by_name = serializers.CharField(source="deleted_by.username", read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    display_status = serializers.CharField(read_only=True)

    class Meta:
        model = StockOutput
        fields = "__all__"
        read_only_fields = [
            "number",
            "user",
            "status",
            "total_value",
            "confirmed_at",
            "cancelled_at",
            "cancelled_by",
            "deleted_at",
            "deleted_by",
            "deletion_reason",
            "created_at",
            "updated_at",
        ]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Inclua ao menos um produto.")
        return items

    def validate(self, attrs):
        reason = attrs.get("reason", getattr(self.instance, "reason", None))
        payment_method = attrs.get(
            "payment_method", getattr(self.instance, "payment_method", StockOutput.PAYMENT_NONE)
        )
        amount_received = attrs.get(
            "amount_received", getattr(self.instance, "amount_received", 0)
        )
        if reason != "COMMERCIAL":
            attrs["payment_method"] = StockOutput.PAYMENT_NONE
            attrs["amount_received"] = 0
            attrs["payment_reference"] = ""
        elif payment_method == StockOutput.PAYMENT_CASH and amount_received is None:
            attrs["amount_received"] = 0
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        output = StockOutput.objects.create(user=self.context["request"].user, **validated_data)
        for item in items:
            StockOutputItem.objects.create(output=output, **item)
        output.recalculate_total()
        return output

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.is_deleted:
            raise serializers.ValidationError("Uma saída excluída não pode ser alterada.")
        if instance.status == StockOutput.CANCELLED:
            raise serializers.ValidationError(
                "Uma saída cancelada é mantida apenas para histórico e não pode ser editada."
            )

        request_user = self.context["request"].user
        items = validated_data.pop("items", None)
        was_confirmed = instance.status == StockOutput.CONFIRMED

        try:
            if was_confirmed:
                instance.cancel(request_user)
                instance.refresh_from_db()
                instance.status = StockOutput.DRAFT
                instance.confirmed_at = None
                instance.cancelled_at = None
                instance.cancelled_by = None
                instance.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "cancelled_at",
                        "cancelled_by",
                        "updated_at",
                    ]
                )

            for key, value in validated_data.items():
                setattr(instance, key, value)
            instance.save()

            if items is not None:
                instance.items.all().delete()
                for item in items:
                    StockOutputItem.objects.create(output=instance, **item)

            if not instance.items.exists():
                raise serializers.ValidationError({"items": "Inclua ao menos um produto."})

            instance.recalculate_total()
            if was_confirmed:
                instance.confirm(request_user, require_payment=True)
            instance.refresh_from_db()
            return instance
        except DjangoValidationError as exc:
            raise serializers.ValidationError(validation_detail(exc)) from exc


class MovementSerializer(serializers.ModelSerializer):
    quantity = IntegerQuantityField(min_value=1)
    previous_stock = IntegerQuantityField(read_only=True)
    final_stock = IntegerQuantityField(read_only=True)
    unit_cost = MoneyField(max_digits=12, min_value=0, required=False)
    unit_sale_price = MoneyField(max_digits=12, min_value=0, required=False)
    product_name = serializers.CharField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    lot_number = serializers.CharField(source="lot.number", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    total_value = MoneyField(max_digits=18, read_only=True)

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
            "product_name_snapshot",
            "product_code_snapshot",
            "category_name_snapshot",
            "unit_snapshot",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        product = attrs.get("product")
        lot = attrs.get("lot")
        if not product:
            raise serializers.ValidationError({"product": "Selecione um produto ativo."})
        if lot and lot.product_id != product.id:
            raise serializers.ValidationError({"lot": "O lote não pertence ao produto selecionado."})
        if attrs.get("type") not in {
            Movement.ENTRY,
            Movement.OUTPUT,
            Movement.ADJUSTMENT_IN,
            Movement.ADJUSTMENT_OUT,
        }:
            raise serializers.ValidationError(
                {"type": "Use entradas, saídas ou ajustes para movimentações manuais."}
            )
        return attrs

    def create(self, validated_data):
        try:
            return Movement.register(user=self.context["request"].user, **validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(validation_detail(exc)) from exc



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
