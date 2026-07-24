from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import Category, Lot, Product, ProductSupplier, Supplier
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


class ProductSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["stock", "created_at", "updated_at"]

    def validate_code(self, value):
        return value.strip()

    def validate_unit(self, value):
        return (value or "UN").strip().upper()

    def validate(self, attrs):
        minimum = attrs.get("minimum_stock", getattr(self.instance, "minimum_stock", 0))
        maximum = attrs.get("maximum_stock", getattr(self.instance, "maximum_stock", 0))
        if maximum and maximum < minimum:
            raise serializers.ValidationError(
                {"maximum_stock": "O estoque máximo não pode ser menor que o mínimo."}
            )
        return attrs


class LotSerializer(serializers.ModelSerializer):
    received_quantity = IntegerQuantityField(read_only=True)
    quantity = IntegerQuantityField(read_only=True)
    cost_price = MoneyField(max_digits=12, read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status = serializers.CharField(read_only=True)
    expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lot
        fields = "__all__"
        read_only_fields = [
            "quantity",
            "received_quantity",
            "created_at",
            "updated_at",
        ]
