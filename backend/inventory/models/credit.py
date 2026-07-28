from django.core.exceptions import ValidationError
from django.db import models, transaction

from .output import StockOutput


# Mantém a alteração isolada sem quebrar o histórico da model principal.
# A migration 0013 cria a coluna correspondente no banco.
if not hasattr(StockOutput, "payment_due_date"):
    StockOutput.add_to_class(
        "payment_due_date",
        models.DateField(null=True, blank=True),
    )


_original_recalculate_total = StockOutput.recalculate_total
_original_validate_checkout = StockOutput.validate_checkout
_original_confirm = StockOutput.confirm


def recalculate_total_with_credit_date(self, save=True):
    total = _original_recalculate_total(self, save=save)
    update_fields = []

    if self.payment_method != self.PAYMENT_ON_ACCOUNT:
        if self.payment_due_date is not None:
            self.payment_due_date = None
            update_fields.append("payment_due_date")
    elif self.status != self.CONFIRMED and self.amount_received:
        # Venda a prazo só passa a ter valor recebido quando o pagamento é confirmado.
        self.amount_received = 0
        update_fields.append("amount_received")

    if save and update_fields:
        update_fields.append("updated_at")
        self.save(update_fields=update_fields)

    return total


def validate_checkout_with_credit_date(self, require_payment=True):
    _original_validate_checkout(self, require_payment=require_payment)

    if self.reason != "COMMERCIAL" or self.payment_method != self.PAYMENT_ON_ACCOUNT:
        return

    if not str(self.customer_name or "").strip():
        raise ValidationError(
            "Informe o nome do cliente para registrar uma venda a prazo/fiado."
        )

    if not self.payment_due_date:
        raise ValidationError(
            "Informe a data prevista para recebimento da venda a prazo/fiado."
        )


def confirm_with_credit_payment(self, user=None, require_payment=False):
    with transaction.atomic():
        result = _original_confirm(
            self,
            user=user,
            require_payment=require_payment,
        )
        if result.payment_method == result.PAYMENT_ON_ACCOUNT:
            result.amount_received = result.total_value
            result.save(update_fields=["amount_received", "updated_at"])
            self.amount_received = result.amount_received
        return result


@property
def payment_status(self):
    if self.reason != "COMMERCIAL" or self.payment_method in {
        self.PAYMENT_NONE,
        "",
        None,
    }:
        return "NOT_APPLICABLE"
    return "PAID" if self.status == self.CONFIRMED else "PENDING"


@property
def payment_status_display(self):
    return {
        "PAID": "Pago",
        "PENDING": "Pendente",
        "NOT_APPLICABLE": "Não se aplica",
    }[self.payment_status]


@property
def payment_overdue(self):
    if (
        self.payment_status != "PENDING"
        or self.payment_method != self.PAYMENT_ON_ACCOUNT
        or not self.payment_due_date
    ):
        return False
    from django.utils import timezone

    return self.payment_due_date < timezone.localdate()


StockOutput.recalculate_total = recalculate_total_with_credit_date
StockOutput.validate_checkout = validate_checkout_with_credit_date
StockOutput.confirm = confirm_with_credit_payment
StockOutput.payment_status = payment_status
StockOutput.payment_status_display = payment_status_display
StockOutput.payment_overdue = payment_overdue
