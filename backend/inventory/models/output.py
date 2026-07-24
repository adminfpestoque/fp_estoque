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
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deleted_outputs",
    )
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-output_date", "-created_at"]
        indexes = [models.Index(fields=["status", "output_date"], name="inv_output_status_date_idx")]

    def save(self, *args, **kwargs):
        self.ensure_number("SAI")
        super().save(*args, **kwargs)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_status(self):
        return "Excluída" if self.is_deleted else self.get_status_display()

    def confirm(self, user=None):
        if self.is_deleted:
            raise ValidationError("Uma saída excluída não pode ser confirmada.")
        if self.status == self.CONFIRMED:
            raise ValidationError("Esta saída já foi confirmada.")
        if self.status == self.CANCELLED:
            raise ValidationError("Uma saída cancelada não pode ser confirmada.")
        if not self.items.exists():
            raise ValidationError("Inclua ao menos um item antes de confirmar.")

        with transaction.atomic():
            locked = StockOutput.objects.select_for_update().get(pk=self.pk)
            if locked.status != self.DRAFT or locked.deleted_at:
                raise ValidationError("A saída não está mais disponível para confirmação.")
            for item in locked.items.select_related("product", "lot"):
                if not item.product_id:
                    raise ValidationError("Um item da saída está sem produto vinculado.")
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
            locked.cancelled_at = None
            locked.cancelled_by = None
            locked.save(
                update_fields=[
                    "status",
                    "confirmed_at",
                    "cancelled_at",
                    "cancelled_by",
                    "updated_at",
                ]
            )
            self.status = locked.status
            self.confirmed_at = locked.confirmed_at
            self.cancelled_at = None
            self.cancelled_by = None
        return self

    def cancel(self, user):
        if self.is_deleted:
            raise ValidationError("Esta saída já está excluída.")
        if self.status != self.CONFIRMED:
            raise ValidationError("Somente saídas confirmadas podem ser canceladas.")
        with transaction.atomic():
            from .movement import Movement

            locked = StockOutput.objects.select_for_update().get(pk=self.pk)
            movements = list(
                locked.movements.filter(reversed=False).select_related("product", "lot")
            )
            for original in movements:
                Movement.reverse(
                    original=original,
                    user=user,
                    reason=f"Cancelamento da saída {locked.number}",
                )
            locked.status = self.CANCELLED
            locked.cancelled_at = timezone.now()
            locked.cancelled_by = user
            locked.save(
                update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"]
            )
            self.status = locked.status
            self.cancelled_at = locked.cancelled_at
            self.cancelled_by = user
        return self

    def soft_delete(self, user, reason=""):
        if self.is_deleted:
            raise ValidationError("Esta saída já foi excluída.")
        with transaction.atomic():
            if self.status == self.CONFIRMED:
                self.cancel(user)
                self.refresh_from_db()
            self.deleted_at = timezone.now()
            self.deleted_by = user
            self.deletion_reason = (reason or "").strip()
            self.save(
                update_fields=["deleted_at", "deleted_by", "deletion_reason", "updated_at"]
            )
        return self


class StockOutputItem(TimeStamped):
    output = models.ForeignKey(StockOutput, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="output_items",
    )
    product_name_snapshot = models.CharField(max_length=180, blank=True)
    product_code_snapshot = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="output_items")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="inv_output_item_qty_valid")]

    def save(self, *args, **kwargs):
        if self.product_id:
            self.product_name_snapshot = self.product.name
            self.product_code_snapshot = self.product.code
        super().save(*args, **kwargs)

    @property
    def product_name(self):
        return self.product.name if self.product_id else self.product_name_snapshot

    @property
    def product_code(self):
        return self.product.code if self.product_id else self.product_code_snapshot
