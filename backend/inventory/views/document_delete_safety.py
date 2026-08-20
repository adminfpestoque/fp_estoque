import logging
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from .documents import SoftDeletedDocumentViewSet, StockEntryViewSet


logger = logging.getLogger(__name__)
_original_destroy = SoftDeletedDocumentViewSet.destroy
_original_entry_cancel = StockEntryViewSet.cancel


def _document_snapshot(view, pk):
    """Consulta apenas o estado essencial sem carregar relações do documento."""
    model = view.queryset.model
    return (
        model._default_manager.filter(pk=pk)
        .only("pk", "number", "status", "deleted_at", "deletion_reason")
        .first()
    )


def _entry_snapshot(pk):
    model = StockEntryViewSet.queryset.model
    return (
        model._default_manager.filter(pk=pk)
        .only("pk", "number", "status", "cancelled_at", "deleted_at")
        .first()
    )


def _cancelled_entry_response(entry):
    return Response(
        {
            "id": entry.pk,
            "number": entry.number,
            "status": entry.status,
            "display_status": "Cancelada",
            "is_deleted": bool(entry.deleted_at),
            "cancelled_at": entry.cancelled_at,
        },
        status=status.HTTP_200_OK,
    )


@wraps(_original_entry_cancel)
def resilient_entry_cancel(self, request, *args, **kwargs):
    """Não devolve falso 500 quando o cancelamento já foi persistido.

    O endpoint normalmente serializa o documento inteiro depois do estorno. Se uma
    relação auxiliar estiver inconsistente e essa etapa falhar, consultamos o estado
    mínimo diretamente. Se a entrada já estiver CANCELLED, confirmamos o sucesso em
    vez de induzir uma segunda tentativa de estorno.
    """
    try:
        return _original_entry_cancel(self, request, *args, **kwargs)
    except Exception as exc:
        pk = kwargs.get("pk")
        entry = None
        try:
            entry = _entry_snapshot(pk)
        except Exception:
            logger.exception(
                "Falha ao consultar entrada após erro no cancelamento.",
                extra={"entry_pk": pk},
            )

        if entry is not None and entry.status == "CANCELLED":
            logger.exception(
                "Entrada já estava cancelada após falha de etapa posterior; retornando sucesso idempotente.",
                extra={"entry_pk": entry.pk, "entry_number": entry.number},
            )
            return _cancelled_entry_response(entry)

        if isinstance(exc, (IntegrityError, ObjectDoesNotExist)):
            logger.exception(
                "Conflito de integridade ao cancelar entrada de estoque.",
                extra={"entry_pk": pk},
            )
            return Response(
                {
                    "detail": (
                        "Não foi possível cancelar esta entrada porque um vínculo do estoque "
                        "ou do histórico está inconsistente. Atualize a tela e tente novamente; "
                        "se o problema persistir, consulte as movimentações relacionadas à entrada."
                    ),
                    "status_code": status.HTTP_409_CONFLICT,
                },
                status=status.HTTP_409_CONFLICT,
            )

        raise


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


StockEntryViewSet.cancel = resilient_entry_cancel
SoftDeletedDocumentViewSet.destroy = resilient_document_destroy
