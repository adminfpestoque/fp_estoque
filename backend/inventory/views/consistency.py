from functools import wraps

from django.db.models import Q
from rest_framework import mixins, status
from rest_framework.response import Response

from ..models import Alert, StockEntry, StockOutput
from ..services import audit, notify_users, refresh_alerts
from .alerts import AlertViewSet, NotificationViewSet
from .documents import (
    MovementViewSet,
    StockEntryViewSet,
    StockOutputViewSet,
)
from .inventories import InventoryViewSet


AlertViewSet.filterset_fields = [
    *AlertViewSet.filterset_fields,
    "output",
]
AlertViewSet.search_fields = [
    *AlertViewSet.search_fields,
    "output__number",
    "output__customer_name",
]


_original_notification_queryset = NotificationViewSet.get_queryset


def notification_queryset_with_output(self):
    queryset = _original_notification_queryset(self).select_related(
        "alert__output",
    )
    alert_type = str(self.request.query_params.get("alert_type") or "").strip()
    if alert_type:
        queryset = queryset.filter(alert__type=alert_type)

    alert_group = str(self.request.query_params.get("alert_group") or "").strip().lower()
    group_types = {
        "credit": [Alert.CREDIT_DUE, Alert.CREDIT_OVERDUE],
        "stock": [Alert.LOW_STOCK, Alert.OUT_OF_STOCK],
        "expiration": [Alert.EXPIRING, Alert.EXPIRED],
        "inventory": [Alert.INVENTORY_DIVERGENCE],
    }
    if alert_group == "system":
        queryset = queryset.filter(alert__isnull=True)
    elif alert_group in group_types:
        queryset = queryset.filter(alert__type__in=group_types[alert_group])
    return queryset


NotificationViewSet.get_queryset = notification_queryset_with_output


def notification_list_without_duplicate_sync(self, request, *args, **kwargs):
    # O resumo e as ações operacionais já sincronizam os alertas. A listagem
    # apenas consulta os dados para evitar duas varreduras completas por tela.
    return mixins.ListModelMixin.list(self, request, *args, **kwargs)


NotificationViewSet.list = notification_list_without_duplicate_sync


_original_notification_summary = NotificationViewSet.summary


@wraps(_original_notification_summary)
def notification_summary_with_deletable_count(self, request, *args, **kwargs):
    response = _original_notification_summary(self, request, *args, **kwargs)
    queryset = self.get_queryset()
    response.data["deletable_read_count"] = queryset.filter(read=True).filter(
        Q(alert__isnull=True) | Q(alert__active=False)
    ).count()
    return response


NotificationViewSet.summary = notification_summary_with_deletable_count


def notification_destroy_preserving_active_alert(self, request, *args, **kwargs):
    notification = self.get_object()
    if notification.alert_id and notification.alert.active:
        return Response(
            {
                "detail": (
                    "Esta notificação pertence a uma situação que ainda está ativa. "
                    "Marque-a como lida; ela poderá ser excluída quando a situação for resolvida."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )
    notification.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


NotificationViewSet.destroy = notification_destroy_preserving_active_alert


def clear_read_preserving_active_alerts(self, request, *args, **kwargs):
    queryset = self.get_queryset().filter(read=True)
    deletable = queryset.filter(
        Q(alert__isnull=True) | Q(alert__active=False)
    )
    preserved_active = queryset.filter(alert__active=True).count()
    deleted, _ = deletable.delete()
    return Response(
        {
            "deleted": deleted,
            "preserved_active": preserved_active,
        }
    )


NotificationViewSet.clear_read = clear_read_preserving_active_alerts


def perform_entry_update_without_notification_noise(self, serializer):
    was_confirmed = serializer.instance.status == StockEntry.CONFIRMED
    entry = serializer.save()
    refresh_alerts(notify=True)
    audit(
        self.request.user,
        "UPDATE",
        entry,
        f"Entrada {entry.number} atualizada.",
    )
    if was_confirmed:
        notify_users(
            "Entrada recalculada",
            (
                f"A entrada {entry.number} foi corrigida e o estoque foi "
                f"recalculado por {self.request.user.username}."
            ),
            level=Alert.WARNING,
        )


StockEntryViewSet.perform_update = perform_entry_update_without_notification_noise


def perform_output_create_with_credit_notice(self, serializer):
    output = serializer.save()
    audit(
        self.request.user,
        "CREATE",
        output,
        f"Saída {output.number} criada como rascunho.",
    )
    if (
        output.reason == "COMMERCIAL"
        and output.payment_method == StockOutput.PAYMENT_ON_ACCOUNT
        and output.payment_due_date
    ):
        refresh_alerts(notify=True)
        notify_users(
            "Venda a prazo pendente",
            (
                f"A saída {output.number}, do cliente "
                f"{output.customer_name or 'não informado'}, foi registrada "
                f"com pagamento pendente."
            ),
            level=Alert.WARNING,
        )


StockOutputViewSet.perform_create = perform_output_create_with_credit_notice


def perform_output_update_without_notification_noise(self, serializer):
    instance = serializer.instance
    was_confirmed = instance.status == StockOutput.CONFIRMED
    old_method = instance.payment_method
    old_due_date = instance.payment_due_date

    output = serializer.save()
    refresh_alerts(notify=True)
    audit(
        self.request.user,
        "UPDATE",
        output,
        f"Saída {output.number} atualizada.",
    )

    if was_confirmed:
        notify_users(
            "Saída recalculada",
            (
                f"A saída {output.number} foi corrigida e o estoque foi "
                f"recalculado por {self.request.user.username}."
            ),
            level=Alert.WARNING,
        )
    elif (
        output.status == StockOutput.DRAFT
        and output.payment_method == StockOutput.PAYMENT_ON_ACCOUNT
        and (
            old_method != StockOutput.PAYMENT_ON_ACCOUNT
            or old_due_date != output.payment_due_date
        )
    ):
        notify_users(
            "Prazo de pagamento atualizado",
            (
                f"O prazo da saída {output.number}, do cliente "
                f"{output.customer_name or 'não informado'}, foi atualizado."
            ),
            level=Alert.INFO,
        )


StockOutputViewSet.perform_update = perform_output_update_without_notification_noise


_original_movement_reverse = MovementViewSet.reverse


@wraps(_original_movement_reverse)
def reverse_only_independent_movement(self, request, pk=None):
    movement = self.get_object()
    if movement.entry_id or movement.output_id:
        document = movement.entry.number if movement.entry_id else movement.output.number
        document_type = "entrada" if movement.entry_id else "saída"
        return Response(
            {
                "detail": (
                    f"Esta movimentação pertence à {document_type} {document}. "
                    f"Cancele o documento correspondente para realizar o estorno "
                    f"sem quebrar o histórico."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )
    return _original_movement_reverse(self, request, pk=pk)


MovementViewSet.reverse = reverse_only_independent_movement


def _refresh_after_success(view_class, method_name):
    original = getattr(view_class, method_name)

    @wraps(original)
    def wrapped(self, request, *args, **kwargs):
        response = original(self, request, *args, **kwargs)
        if getattr(response, "status_code", 500) < 400:
            refresh_alerts(notify=True)
        return response

    setattr(view_class, method_name, wrapped)


for _inventory_action in (
    "add_item",
    "bulk_count",
    "submit",
    "reopen",
    "cancel",
):
    _refresh_after_success(InventoryViewSet, _inventory_action)
