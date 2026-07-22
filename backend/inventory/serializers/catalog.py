from rest_framework import serializers

from ..models import Category, Lot, Product, ProductSupplier, Supplier
from ..validators import validate_document

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SupplierSerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(read_only=True)
    entries_count = serializers.IntegerField(read_only=True)
    entries_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, allow_null=True)
    last_entry = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate_document(self, value):
        return validate_document(value) if value else value


class ProductSupplierSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = ProductSupplier
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    lots_count = serializers.IntegerField(read_only=True)
    supplier_links = ProductSupplierSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["stock", "created_at", "updated_at"]

    def validate(self, attrs):
        minimum = attrs.get("minimum_stock", getattr(self.instance, "minimum_stock", 0))
        maximum = attrs.get("maximum_stock", getattr(self.instance, "maximum_stock", 0))
        if maximum and maximum < minimum:
            raise serializers.ValidationError({"maximum_stock": "O estoque máximo não pode ser menor que o mínimo."})
        return attrs


class LotSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status = serializers.CharField(read_only=True)
    expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lot
        fields = "__all__"
        read_only_fields = ["quantity", "received_quantity", "created_at", "updated_at"]


