from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument, TimeStamped
from .catalog import Lot, Product

class StockOutput(NumberedDocument):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    STATUSES = [(DRAFT, "Rascunho"), (CONFIRMED, "Confirmada"), (CANCELLED, "Cancelada")]
    REASONS = [
        ("COMMERCIAL", "Retirada para comercialização"),
        ("TRANSFER", "Transferência"),
        ("LOSS", "Perda"),
        ("DAMAGE", "Avaria"),
        ("EXPIRED", "Produto vencido"),
        ("INTERNAL", "Consumo interno"),
        ("DONATION", "Doação"),
        ("ADJUSTMENT", "Ajuste"),
        ("OTHER", "Outros"),
    ]

    output_date = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_outputs")
    reason = models.CharField(max_length=20, choices=REASONS)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_outputs",
    )

    class Meta:
        ordering = ["-output_date", "-created_at"]
        indexes = [models.Index(fields=["status", "output_date"], name="inv_output_status_date_idx")]

    def save(self, *args, **kwargs):
        self.ensure_number("SAI")
        super().save(*args, **kwargs)

    def confirm(self, user=None):
        if self.status == self.CONFIRMED:
            raise ValidationError("Esta saída já foi confirmada.")
        if self.status == self.CANCELLED:
            raise ValidationError("Uma saída cancelada não pode ser confirmada.")
        if not self.items.exists():
            raise ValidationError("Inclua ao menos um item antes de confirmar.")

        with transaction.atomic():
            locked = StockOutput.objects.select_for_update().get(pk=self.pk)
            if locked.status != self.DRAFT:
                raise ValidationError("A saída não está mais em rascunho.")
            for item in locked.items.select_related("product", "lot"):
                if item.product.stock < item.quantity:
                    raise ValidationError(f"Estoque insuficiente para {item.product.name}.")
                from .movement import Movement
                Movement.consume_fefo(
                    product=item.product,
                    quantity=item.quantity,
                    user=user or locked.user,
                    preferred_lot=item.lot,
                    reason=locked.get_reason_display(),
                    notes=item.notes or locked.notes,
                    document=locked.number,
                    output=locked,
                )
            locked.status = self.CONFIRMED
            locked.confirmed_at = timezone.now()
            locked.save(update_fields=["status", "confirmed_at", "updated_at"])
            self.status = locked.status
            self.confirmed_at = locked.confirmed_at
        return self

    def cancel(self, user):
        if self.status != self.CONFIRMED:
            raise ValidationError("Somente saídas confirmadas podem ser canceladas.")
        with transaction.atomic():
            from .movement import Movement
            locked = StockOutput.objects.select_for_update().get(pk=self.pk)
            for original in locked.movements.filter(reversed=False).select_related("product", "lot"):
                Movement.reverse(original=original, user=user, reason=f"Cancelamento da saída {locked.number}")
            locked.status = self.CANCELLED
            locked.cancelled_at = timezone.now()
            locked.cancelled_by = user
            locked.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
            self.status = locked.status
        return self


class StockOutputItem(TimeStamped):
    output = models.ForeignKey(StockOutput, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="output_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="output_items")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="inv_output_item_qty_valid")]


