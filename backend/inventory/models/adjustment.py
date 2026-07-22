from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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

    def confirm(self, user=None):
        if self.status != self.DRAFT:
            raise ValidationError("Somente ajustes em rascunho podem ser confirmados.")
        movement = Movement.register(
            product=self.product,
            lot=self.lot,
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
        self.save(update_fields=["movement", "status", "confirmed_at", "updated_at"])
        return self

    def cancel(self, user):
        if self.status != self.CONFIRMED or not self.movement:
            raise ValidationError("Somente ajustes confirmados podem ser cancelados.")
        Movement.reverse(original=self.movement, user=user, reason=f"Cancelamento do ajuste {self.number}")
        self.status = self.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])
        return self


