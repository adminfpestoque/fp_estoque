from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response

from ..models import PackagingType
from ..services import audit
from .catalog import PackagingTypeViewSet, ProductViewSet


def packaging_queryset(self):
    queryset = PackagingType.objects.annotate(
        products_count=Count(
            "products",
            filter=Q(products__isnull=False),
            distinct=True,
        )
        + Count(
            "product_options",
            filter=Q(product_options__isnull=False),
            distinct=True,
        ),
    ).order_by("name")
    kind = str(self.request.query_params.get("kind") or "").strip().upper()
    if kind == PackagingType.CONTAINER:
        queryset = queryset.filter(kind__in=[PackagingType.CONTAINER, PackagingType.BOTH])
    elif kind == PackagingType.GROUPING:
        queryset = queryset.filter(kind__in=[PackagingType.GROUPING, PackagingType.BOTH])
    elif kind == PackagingType.BOTH:
        queryset = queryset.filter(kind=PackagingType.BOTH)
    return queryset


def destroy_packaging(self, request, *args, **kwargs):
    packaging_type = self.get_object()
    product_count = packaging_type.products.count()
    grouping_count = packaging_type.product_options.count()
    total_count = product_count + grouping_count
    if total_count:
        return Response(
            {
                "detail": (
                    "Esta opção está sendo usada por produtos. "
                    "Altere os produtos vinculados ou inative a opção."
                ),
                "products_count": total_count,
                "can_deactivate": packaging_type.active,
            },
            status=status.HTTP_409_CONFLICT,
        )
    name = packaging_type.name
    packaging_type.delete()
    audit(request.user, "DELETE", None, f'Embalagem ou tipo "{name}" excluído.')
    return Response(status=status.HTTP_204_NO_CONTENT)


PackagingTypeViewSet.get_queryset = packaging_queryset
PackagingTypeViewSet.destroy = destroy_packaging
if "kind" not in PackagingTypeViewSet.filterset_fields:
    PackagingTypeViewSet.filterset_fields = [*PackagingTypeViewSet.filterset_fields, "kind"]

_original_product_queryset = ProductViewSet.get_queryset


def product_queryset(self):
    return _original_product_queryset(self).select_related("packaging")


ProductViewSet.get_queryset = product_queryset
if "packaging" not in ProductViewSet.filterset_fields:
    ProductViewSet.filterset_fields = [*ProductViewSet.filterset_fields, "packaging"]
if "packaging__name" not in ProductViewSet.search_fields:
    ProductViewSet.search_fields = [*ProductViewSet.search_fields, "packaging__name"]
