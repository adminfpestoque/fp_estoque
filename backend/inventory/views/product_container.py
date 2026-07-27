from django.db.models import Count
from rest_framework import status
from rest_framework.response import Response

from ..models import PackagingType
from ..services import audit
from .catalog import PackagingTypeViewSet, ProductViewSet


def packaging_queryset(self):
    return PackagingType.objects.annotate(
        products_count=Count("products", distinct=True),
    ).order_by("name")


def destroy_packaging(self, request, *args, **kwargs):
    packaging_type = self.get_object()
    product_count = packaging_type.products.count()
    legacy_count = packaging_type.product_options.count()
    total_count = product_count + legacy_count
    if total_count:
        return Response(
            {
                "detail": (
                    "Esta embalagem está sendo usada por produtos. "
                    "Altere os produtos vinculados ou inative a embalagem."
                ),
                "products_count": total_count,
                "can_deactivate": packaging_type.active,
            },
            status=status.HTTP_409_CONFLICT,
        )
    name = packaging_type.name
    packaging_type.delete()
    audit(request.user, "DELETE", None, f'Embalagem "{name}" excluída.')
    return Response(status=status.HTTP_204_NO_CONTENT)


PackagingTypeViewSet.get_queryset = packaging_queryset
PackagingTypeViewSet.destroy = destroy_packaging

_original_product_queryset = ProductViewSet.get_queryset


def product_queryset(self):
    return _original_product_queryset(self).select_related("packaging")


ProductViewSet.get_queryset = product_queryset
if "packaging" not in ProductViewSet.filterset_fields:
    ProductViewSet.filterset_fields = [*ProductViewSet.filterset_fields, "packaging"]
if "packaging__name" not in ProductViewSet.search_fields:
    ProductViewSet.search_fields = [*ProductViewSet.search_fields, "packaging__name"]
