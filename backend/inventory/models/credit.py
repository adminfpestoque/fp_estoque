from django.core.exceptions import ValidationError
from django.db import models

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


def recalculate_total_with_credit_date(self, save=True):
    total = _original_recalculate_total(self, save=save)

    if self.payment_method != self.PAYMENT_ON_ACCOUNT and self.payment_due_date is not None:
        self.payment_due_date = None
        if save:
            self.save(update_fields=["payment_due_date", "updated_at"])

    return total


def validate_checkout_with_credit_date(self, require_payment=True):
    _original_validate_checkout(self, require_payment=require_payment)

    if self.reason != "COMMERCIAL" or self.payment_method != self.PAYMENT_ON_ACCOUNT:
        return

    if not str(self.customer_name or "").strip():
        raise ValidationError("Informe o nome do cliente para registrar uma venda a prazo/fiado.")

    if not self.payment_due_date:
        raise ValidationError("Informe a data prevista para recebimento da venda a prazo/fiado.")


StockOutput.recalculate_total = recalculate_total_with_credit_date
StockOutput.validate_checkout = validate_checkout_with_credit_date
