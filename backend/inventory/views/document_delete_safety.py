import logging
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from .documents import SoftDeletedDocumentViewSet


logger = logging.getLogger(__name__)
_original_destroy = SoftDeletedDocumentViewSet.destroy


def _document_snapshot(view, pk):
    """Consulta apenas o estado essencial sem carregar relações do documento."""
    model = view.queryset.model
    return (
        model._default_manager.filter(pk=pk)
        .only("pk", "number", "status", "deleted_at", "deletion_reason")
        .first()
    )


@wraps(_original_destroy)
def resilient_document_destroy(self, request, *args, **kwargs):
    """Torna a exclusão lógica idempotente e evita falso erro 500 pós-exclusão.

    A parte crítica do estoque é executada dentro de transação pelos próprios
    modelos. Se uma etapa posterior falhar depois de ``deleted_at`` ter sido
    persistido, retornar erro induziria o usuário a repetir uma operação que já
    aconteceu. Nesse caso a API confirma o estado final e a interface recarrega
    normalmente.
    """
    try:
        return _original_destroy(self, request, *args, **kwargs)
    except Exception as exc:
        pk = kwargs.get("pk")
        document = None
        try:
            document = _document_snapshot(self, pk)
        except Exception:
            logger.exception(
                "Falha ao consultar documento após erro na exclusão.",
                extra={"document_pk": pk, "document_type": self.deleted_label},
            )

        if document is not None and document.deleted_at is not None:
            logger.exception(
                "Documento já estava excluído após falha de etapa posterior; retornando sucesso idempotente.",
                extra={
                    "document_pk": document.pk,
                    "document_number": document.number,
                    "document_type": self.deleted_label,
                },
            )
            return Response(
                {
                    "id": document.pk,
                    "number": document.number,
                    "status": document.status,
                    "is_deleted": True,
                    "display_status": "Excluída",
                    "deletion_reason": document.deletion_reason,
                },
                status=status.HTTP_200_OK,
            )

        if isinstance(exc, (IntegrityError, ObjectDoesNotExist)):
            logger.exception(
                "Conflito de integridade ao excluir documento de estoque.",
                extra={"document_pk": pk, "document_type": self.deleted_label},
            )
            label = str(self.deleted_label or "registro").lower()
            return Response(
                {
                    "detail": (
                        f"Não foi possível excluir esta {label} porque o estoque ou o histórico "
                        "relacionado não pode ser estornado com segurança. Atualize a tela e "
                        "verifique as movimentações dependentes antes de tentar novamente."
                    ),
                    "status_code": status.HTTP_409_CONFLICT,
                },
                status=status.HTTP_409_CONFLICT,
            )

        raise


SoftDeletedDocumentViewSet.destroy = resilient_document_destroy
