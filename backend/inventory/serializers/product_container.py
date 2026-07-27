from rest_framework import serializers

from ..models import PackagingType
from .catalog import ProductPackagingSerializer, ProductSerializer


ProductSerializer._declared_fields["packaging_name"] = serializers.CharField(
    source="packaging.name",
    read_only=True,
)


if not getattr(ProductSerializer, "_simple_packaging_installed", False):
    _original_validate = ProductSerializer.validate

    def validate_with_packaging(self, attrs):
        attrs = _original_validate(self, attrs)
        # O custo é definido exclusivamente pelas entradas de estoque.
        attrs.pop("cost_price", None)
        packaging = attrs.get(
            "packaging",
            getattr(self.instance, "packaging", None),
        )
        if packaging is not None:
            if packaging.kind not in [PackagingType.CONTAINER, PackagingType.BOTH]:
                raise serializers.ValidationError(
                    {"packaging": "Selecione uma embalagem do produto, como lata ou garrafa."}
                )
            if not packaging.active:
                current_id = getattr(self.instance, "packaging_id", None)
                if not self.instance or current_id != packaging.pk:
                    raise serializers.ValidationError(
                        {"packaging": "A embalagem selecionada está inativa."}
                    )
        return attrs

    ProductSerializer.validate = validate_with_packaging
    ProductSerializer._simple_packaging_installed = True


if not getattr(ProductPackagingSerializer, "_grouping_kind_installed", False):
    _original_packaging_validate = ProductPackagingSerializer.validate

    def validate_grouping_type(self, attrs):
        attrs = _original_packaging_validate(self, attrs)
        # O custo de caixa, fardo, grade ou pacote é informado em Nova entrada.
        attrs.pop("cost_price", None)
        packaging_type = attrs.get(
            "packaging_type",
            getattr(self.instance, "packaging_type", None),
        )
        if packaging_type and packaging_type.kind not in [
            PackagingType.GROUPING,
            PackagingType.BOTH,
        ]:
            raise serializers.ValidationError(
                {
                    "packaging_type": (
                        "Selecione um tipo de empacotamento, como caixa, fardo ou grade."
                    )
                }
            )
        return attrs

    ProductPackagingSerializer.validate = validate_grouping_type
    ProductPackagingSerializer._grouping_kind_installed = True
