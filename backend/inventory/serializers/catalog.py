from uuid import uuid4

from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    Category,
    Lot,
    Product,
    ProductPackaging,
    ProductSupplier,
    Supplier,
)
from ..validators import validate_document
from .fields import IntegerQuantityField, MoneyField, NullableUniqueCharField


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SupplierSerializer(serializers.ModelSerializer):
    document = NullableUniqueCharField(
        max_length=20,
        validators=[
            UniqueValidator(
                queryset=Supplier.objects.all(),
                message="Já existe um fornecedor com este CPF/CNPJ.",
            )
        ],
    )
    products_count = serializers.IntegerField(read_only=True)
    entries_count = serializers.IntegerField(read_only=True)
    entries_value = MoneyField(max_digits=16, read_only=True, allow_null=True)
    last_entry = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate_document(self, value):
        return validate_document(value) if value else None


class ProductSupplierSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    last_cost = MoneyField(max_digits=12, required=False, min_value=0)

    class Meta:
        model = ProductSupplier
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ProductPackagingSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    units_per_package = IntegerQuantityField(min_value=2)
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = ProductPackaging
        fields = "__all__"
        read_only_fields = ["product", "created_at", "updated_at"]

    def validate_name(self, value):
        name = " ".join(str(value or "").strip().split())
        if not name:
            raise serializers.ValidationError("Informe o nome da forma de saída.")
        return name


class ProductSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        validators=[
            UniqueValidator(
                queryset=Product.objects.all(),
                message="Já existe um produto com este código interno.",
            )
        ],
    )
    sku = NullableUniqueCharField(
        max_length=80,
        validators=[
            UniqueValidator(
                queryset=Product.objects.all(),
                message="Já existe um produto com este SKU.",
            )
        ],
    )
    barcode = NullableUniqueCharField(
        max_length=80,
        validators=[
            UniqueValidator(
                queryset=Product.objects.all(),
                message="Já existe um produto com este código de barras.",
            )
        ],
    )
    package_quantity = IntegerQuantityField(min_value=1, default=1)
    volume = IntegerQuantityField(min_value=1, default=1)
    cost_price = MoneyField(max_digits=12, min_value=0, default=0)
    sale_price = MoneyField(max_digits=12, min_value=0, default=0)
    stock = IntegerQuantityField(read_only=True)
    minimum_stock = IntegerQuantityField(min_value=0, default=0)
    maximum_stock = IntegerQuantityField(min_value=0, default=0)
    category_name = serializers.CharField(source="category.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    low_stock = serializers.BooleanField(read_only=True)
    stock_value = MoneyField(max_digits=18, read_only=True)
    lots_count = serializers.IntegerField(read_only=True)
    supplier_links = ProductSupplierSerializer(many=True, read_only=True)
    packaging_options = ProductPackagingSerializer(many=True, required=False)
    package_description = serializers.CharField(read_only=True)
    deleted_by_name = serializers.CharField(
        source="deleted_by.username", read_only=True, allow_null=True
    )
    is_deleted = serializers.BooleanField(read_only=True)
    display_status = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = [
            "stock",
            "deleted_at",
            "deleted_by",
            "deletion_reason",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value):
        return value.strip()

    def validate_unit(self, value):
        return "UN"

    def validate_volume_unit(self, value):
        return str(value or Product.VOLUME_ML).strip().upper()

    @staticmethod
    def _generate_code():
        while True:
            code = f"PROD-{uuid4().hex[:8].upper()}"
            if not Product.objects.filter(code=code).exists():
                return code

    def _validate_packaging_options(self, options):
        names = set()
        normalized = []
        for option in options or []:
            name = " ".join(str(option.get("name") or "").strip().split())
            key = name.casefold()
            if not name:
                raise serializers.ValidationError(
                    {"packaging_options": "Informe o nome de todas as formas de saída."}
                )
            if key == "unidade":
                raise serializers.ValidationError(
                    {"packaging_options": "Unidade já é a forma padrão e não precisa ser cadastrada."}
                )
            if key in names:
                raise serializers.ValidationError(
                    {"packaging_options": f'A forma de saída "{name}" está repetida.'}
                )
            names.add(key)
            normalized.append({**option, "name": name})
        return normalized

    def validate(self, attrs):
        minimum = attrs.get("minimum_stock", getattr(self.instance, "minimum_stock", 0))
        maximum = attrs.get("maximum_stock", getattr(self.instance, "maximum_stock", 0))
        if maximum and maximum < minimum:
            raise serializers.ValidationError(
                {"maximum_stock": "O estoque máximo não pode ser menor que o mínimo."}
            )
        if "packaging_options" in attrs:
            attrs["packaging_options"] = self._validate_packaging_options(
                attrs.get("packaging_options")
            )
        return attrs

    @staticmethod
    def _sync_packaging_options(product, options):
        existing = {item.id: item for item in product.packaging_options.all()}
        kept_ids = set()
        for data in options:
            option_id = data.pop("id", None)
            if option_id:
                option = existing.get(int(option_id))
                if not option:
                    raise serializers.ValidationError(
                        {"packaging_options": "Uma forma de saída informada não pertence a este produto."}
                    )
                for key, value in data.items():
                    setattr(option, key, value)
                option.save()
                kept_ids.add(option.id)
            else:
                option = ProductPackaging.objects.create(product=product, **data)
                kept_ids.add(option.id)
        product.packaging_options.exclude(id__in=kept_ids).delete()

    @transaction.atomic
    def create(self, validated_data):
        packaging_options = validated_data.pop("packaging_options", [])
        if not validated_data.get("code"):
            validated_data["code"] = self._generate_code()
        validated_data["unit"] = "UN"
        validated_data.setdefault("package_quantity", 1)
        product = super().create(validated_data)
        self._sync_packaging_options(product, packaging_options)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.is_deleted:
            raise serializers.ValidationError(
                "Um produto excluído é mantido apenas para histórico e não pode ser alterado."
            )
        packaging_options = validated_data.pop("packaging_options", None)
        if not validated_data.get("code"):
            validated_data.pop("code", None)
        validated_data["unit"] = "UN"
        product = super().update(instance, validated_data)
        if packaging_options is not None:
            self._sync_packaging_options(product, packaging_options)
        return product


class LotSerializer(serializers.ModelSerializer):
    received_quantity = IntegerQuantityField(read_only=True)
    quantity = IntegerQuantityField(read_only=True)
    cost_price = MoneyField(max_digits=12, read_only=True)
    product_name = serializers.CharField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status = serializers.CharField(read_only=True)
    expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lot
        fields = "__all__"
        read_only_fields = [
            "quantity",
            "received_quantity",
            "product_name_snapshot",
            "product_code_snapshot",
            "created_at",
            "updated_at",
        ]
