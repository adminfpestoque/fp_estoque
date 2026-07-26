from uuid import uuid4

from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    Category,
    Lot,
    PackagingType,
    Product,
    ProductPackaging,
    ProductSupplier,
    Supplier,
)
from ..validators import validate_document
from .fields import IntegerQuantityField, MoneyField, NullableUniqueCharField


class PackagingTypeSerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = PackagingType
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate_name(self, value):
        name = " ".join(str(value or "").strip().split())
        if not name:
            raise serializers.ValidationError("Informe o nome do tipo de embalagem.")
        queryset = PackagingType.objects.filter(name__iexact=name)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Já existe um tipo de embalagem com este nome.")
        if name.casefold() == "unidade":
            raise serializers.ValidationError(
                "Unidade é a forma padrão do sistema e não precisa ser cadastrada."
            )
        return name


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
    name = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    packaging_type = serializers.PrimaryKeyRelatedField(
        queryset=PackagingType.objects.all(),
        required=False,
    )
    packaging_type_name = serializers.CharField(
        source="packaging_type.name",
        read_only=True,
    )
    units_per_package = IntegerQuantityField(min_value=2)
    cost_price = MoneyField(max_digits=12, min_value=0, default=0)
    sale_price = MoneyField(max_digits=12, min_value=0, default=0)
    type_display = serializers.CharField(source="packaging_type.name", read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = ProductPackaging
        fields = "__all__"
        read_only_fields = ["product", "created_at", "updated_at"]

    def validate(self, attrs):
        packaging_type = attrs.get("packaging_type", getattr(self.instance, "packaging_type", None))
        if not packaging_type:
            # Compatibilidade: integrações antigas podem enviar name/type.
            initial = getattr(self, "initial_data", {}) or {}
            raw = attrs.get("name") or initial.get("name") or initial.get("packaging_type_name")
            if raw:
                packaging_type = ProductPackaging.resolve_packaging_type(raw)
                attrs["packaging_type"] = packaging_type
        if not packaging_type:
            raise serializers.ValidationError({"packaging_type": "Selecione o tipo de embalagem."})
        if not packaging_type.active and not self.instance:
            raise serializers.ValidationError({"packaging_type": "O tipo de embalagem está inativo."})
        return attrs


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
        if len(options or []) > 1:
            raise serializers.ValidationError(
                {"packaging_options": "Cadastre somente um tipo de embalagem adicional por produto."}
            )
        type_ids = set()
        normalized = []
        defaults = 0
        for option in options or []:
            packaging_type = option.get("packaging_type")
            if not packaging_type:
                raw_name = option.get("name") or option.get("packaging_type_name")
                if raw_name:
                    packaging_type = ProductPackaging.resolve_packaging_type(raw_name)
                    option["packaging_type"] = packaging_type
            if not packaging_type:
                raise serializers.ValidationError(
                    {"packaging_options": "Selecione o tipo de todas as embalagens."}
                )
            if packaging_type.name.casefold() == "unidade":
                raise serializers.ValidationError(
                    {"packaging_options": "Unidade já é a forma padrão e não precisa ser cadastrada."}
                )
            if packaging_type.pk in type_ids:
                raise serializers.ValidationError(
                    {"packaging_options": f'O tipo "{packaging_type.name}" está repetido.'}
                )
            type_ids.add(packaging_type.pk)
            defaults += 1 if option.get("is_default") else 0
            normalized.append(option)
        if defaults > 1:
            raise serializers.ValidationError(
                {"packaging_options": "Escolha somente uma embalagem padrão."}
            )
        return normalized

    def validate(self, attrs):
        minimum = attrs.get(
            "minimum_stock", getattr(self.instance, "minimum_stock", 0)
        )
        maximum = attrs.get(
            "maximum_stock", getattr(self.instance, "maximum_stock", 0)
        )
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
        for raw_data in options:
            data = dict(raw_data)
            option_id = data.pop("id", None)
            # Campos legados são derivados do catálogo global.
            data.pop("name", None)
            data.pop("type", None)
            if option_id:
                option = existing.get(int(option_id))
                if not option:
                    raise serializers.ValidationError(
                        {"packaging_options": "Uma embalagem informada não pertence a este produto."}
                    )
                for key, value in data.items():
                    setattr(option, key, value)
                option.save()
                kept_ids.add(option.id)
            else:
                option = ProductPackaging.objects.create(product=product, **data)
                kept_ids.add(option.id)

        removed = product.packaging_options.exclude(id__in=kept_ids)
        if removed.filter(entry_items__isnull=False).exists() or removed.filter(output_items__isnull=False).exists():
            removed.update(active=False, is_default=False)
        else:
            removed.delete()

        # Sempre mantém uma forma padrão quando há embalagens ativas.
        active_options = list(product.packaging_options.filter(active=True).order_by("pk"))
        if active_options and not any(option.is_default for option in active_options):
            active_options[0].is_default = True
            active_options[0].save(update_fields=["is_default", "updated_at"])

    @transaction.atomic
    def create(self, validated_data):
        packaging_options = validated_data.pop("packaging_options", [])
        if not validated_data.get("code"):
            validated_data["code"] = self._generate_code()
        validated_data["unit"] = "UN"
        validated_data.setdefault("package_quantity", 1)
        product = super().create(validated_data)
        self._sync_packaging_options(product, packaging_options)
        if packaging_options:
            default_option = product.packaging_options.filter(is_default=True).first()
            if default_option:
                product.package_type = default_option.display_name
                product.save(update_fields=["package_type", "updated_at"])
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
            default_option = product.packaging_options.filter(is_default=True).first()
            product.package_type = default_option.display_name if default_option else ""
            product.save(update_fields=["package_type", "updated_at"])
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
