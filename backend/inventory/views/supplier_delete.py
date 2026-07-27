from rest_framework import status
from rest_framework.response import Response

from ..services import audit
from .catalog import SupplierViewSet


def supplier_deletion_blockers(supplier):
    relations = [
        ("entries", supplier.entries.count(), "entrada(s) registrada(s)"),
        ("primary_products", supplier.primary_products.count(), "produto(s) com este fornecedor principal"),
        ("product_links", supplier.product_links.count(), "vínculo(s) com produtos"),
        ("lots", supplier.lots.count(), "lote(s) vinculado(s)"),
    ]
    return [
        {
            "code": code,
            "count": count,
            "description": f"{count} {description}",
        }
        for code, count, description in relations
        if count
    ]


def destroy_supplier(self, request, *args, **kwargs):
    supplier = self.get_object()
    blockers = supplier_deletion_blockers(supplier)

    if blockers:
        return Response(
            {
                "detail": (
                    "Este fornecedor possui produtos, entradas, lotes ou outros vínculos e não pode ser apagado. "
                    "Altere os vínculos relacionados ou inative o fornecedor para preservar o histórico."
                ),
                "blockers": blockers,
                "can_deactivate": supplier.active,
            },
            status=status.HTTP_409_CONFLICT,
        )

    supplier_name = supplier.name
    supplier_document = supplier.document or ""
    supplier.delete()
    audit(
        request.user,
        "DELETE",
        None,
        f'Fornecedor "{supplier_name}" excluído permanentemente.',
        metadata={
            "supplier_name": supplier_name,
            "supplier_document": supplier_document,
        },
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


SupplierViewSet.destroy = destroy_supplier
