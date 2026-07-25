
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument
from .catalog import Lot, Product
from .movement import Movement


class StockAdjustment(NumberedDocument):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    TYPES = [(POSITIVE, "Positivo"), (NEGATIVE, "Negativo")]
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    STATUSES = [(DRAFT, "Rascunho"), (CONFIRMED, "Confirmado"), (CANCELLED, "Cancelado")]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="adjustments")
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustments")
    type = models.CharField(max_length=10, choices=TYPES)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=200)
    justification = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_adjustments")
    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    movement = models.OneToOneField(Movement, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustment")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="inv_adjustment_qty_valid")]

    def save(self, *args, **kwargs):
        self.ensure_number("AJU")
        super().save(*args, **kwargs)

    def _validate_links(self):
        if self.product.deleted_at is not None:
            raise ValidationError("Um produto excluído não pode receber novos ajustes.")
        if self.lot_id and self.lot.product_id != self.product_id:
            raise ValidationError("O lote não pertence ao produto selecionado.")

    @transaction.atomic
    def confirm(self, user=None):
        if self.status != self.DRAFT:
            raise ValidationError("Somente ajustes em rascunho podem ser confirmados.")

        product = Product.objects.select_for_update().get(pk=self.product_id)
        lot = None
        if self.lot_id:
            lot = Lot.objects.select_for_update().get(pk=self.lot_id)
        self.product = product
        self.lot = lot
        self._validate_links()

        movement = Movement.register(
            product=product,
            lot=lot,
            type=Movement.ADJUSTMENT_IN if self.type == self.POSITIVE else Movement.ADJUSTMENT_OUT,
            quantity=self.quantity,
            user=user or self.user,
            reason=self.reason,
            notes=self.justification,
            document=self.number,
        )
        self.movement = movement
        self.status = self.CONFIRMED
        self.confirmed_at = timezone.now()
        self.cancelled_at = None
        self.save(
            update_fields=[
                "movement",
                "status",
                "confirmed_at",
                "cancelled_at",
                "updated_at",
            ]
        )
        return self

    @transaction.atomic
    def cancel(self, user):
        if self.status != self.CONFIRMED or not self.movement:
            raise ValidationError("Somente ajustes confirmados podem ser cancelados.")
        Movement.reverse(
            original=self.movement,
            user=user,
            reason=f"Cancelamento do ajuste {self.number}",
        )
        self.status = self.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])
        return self
