from django.db import models
from django.db.models import Q


def retire_product_maximum_stock(Product):
    """Remove o limite máximo do modelo em tempo de execução.

    A migração 0014 remove a coluna física do banco. A propriedade legada retorna
    zero e aceita valores antigos sem armazená-los, mantendo compatibilidade com
    integrações e testes que ainda enviam esse campo.
    """
    try:
        field = Product._meta.get_field("maximum_stock")
    except Exception:
        field = None

    if field is not None:
        Product._meta.local_fields = [item for item in Product._meta.local_fields if item.name != "maximum_stock"]
        if hasattr(Product, "maximum_stock"):
            delattr(Product, "maximum_stock")

    def get_retired_maximum_stock(self):
        return 0

    def set_retired_maximum_stock(self, value):
        self.__dict__["_retired_maximum_stock"] = value

    Product.maximum_stock = property(
        get_retired_maximum_stock,
        set_retired_maximum_stock,
    )
    Product._meta.constraints = [
        constraint
        for constraint in Product._meta.constraints
        if constraint.name != "inventory_product_nonnegative_values"
    ]
    Product._meta.constraints.append(
        models.CheckConstraint(
            condition=Q(
                cost_price__gte=0,
                sale_price__gte=0,
                stock__gte=0,
                minimum_stock__gte=0,
                package_quantity__gt=0,
            ),
            name="inventory_product_nonnegative_values",
        )
    )
    Product._meta._expire_cache()


def retire_product_serializer(ProductSerializer):
    ProductSerializer._declared_fields.pop("maximum_stock", None)

    def validate_without_maximum(self, attrs):
        attrs.pop("maximum_stock", None)
        if "packaging_options" in attrs:
            attrs["packaging_options"] = self._validate_packaging_options(
                attrs.get("packaging_options")
            )
        return attrs

    ProductSerializer.validate = validate_without_maximum
