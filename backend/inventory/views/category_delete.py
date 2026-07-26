from rest_framework import status
from rest_framework.response import Response

from ..services import audit
from .catalog import CategoryViewSet


def destroy_category(self, request, *args, **kwargs):
    category = self.get_object()
    products_count = category.products.count()

    if products_count:
        return Response(
            {
                "detail": (
                    "Esta categoria está sendo usada por produtos e não pode ser apagada. "
                    "Altere a categoria desses produtos ou inative a categoria para preservar o histórico."
                ),
                "products_count": products_count,
                "can_deactivate": category.active,
            },
            status=status.HTTP_409_CONFLICT,
        )

    category_name = category.name
    category.delete()
    audit(
        request.user,
        "DELETE",
        None,
        f'Categoria "{category_name}" excluída permanentemente.',
        metadata={"category_name": category_name},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


CategoryViewSet.destroy = destroy_category
