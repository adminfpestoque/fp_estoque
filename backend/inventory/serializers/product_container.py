from rest_framework import serializers

from .catalog import ProductSerializer


ProductSerializer._declared_fields["packaging_name"] = serializers.CharField(
    source="packaging.name",
    read_only=True,
)


if not getattr(ProductSerializer, "_simple_packaging_installed", False):
    _original_validate = ProductSerializer.validate

    def validate_with_packaging(self, attrs):
        attrs = _original_validate(self, attrs)
        packaging = attrs.get(
            "packaging",
            getattr(self.instance, "packaging", None),
        )
        if packaging is None:
            raise serializers.ValidationError(
                {"packaging": "Selecione a embalagem do produto."}
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
