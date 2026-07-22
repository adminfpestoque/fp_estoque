from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument, TimeStamped
from .catalog import Lot, Product, ProductSupplier, Supplier

class StockEntry(NumberedDocument):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    STATUSES = [(DRAFT, "Rascunho"), (CONFIRMED, "Confirmada"), (CANCELLED, "Cancelada")]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="entries")
    entry_date = models.DateTimeField(default=timezone.now)
    invoice_number = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_entries")
    notes = models.TextField(blank=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_entries",
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [models.Index(fields=["status", "entry_date"], name="inv_entry_status_date_idx")]

    def save(self, *args, **kwargs):
        self.ensure_number("ENT")
        super().save(*args, **kwargs)

    def recalculate_total(self):
        total = sum((item.quantity * item.unit_cost for item in self.items.all()), Decimal("0"))
        self.total_value = total
        self.save(update_fields=["total_value", "updated_at"])

    def confirm(self, user=None):
        if self.status == self.CONFIRMED:
            raise ValidationError("Esta entrada já foi confirmada.")
        if self.status == self.CANCELLED:
            raise ValidationError("Uma entrada cancelada não pode ser confirmada.")
        if not self.items.exists():
            raise ValidationError("Inclua ao menos um item antes de confirmar.")

        with transaction.atomic():
            locked = StockEntry.objects.select_for_update().get(pk=self.pk)
            if locked.status != self.DRAFT:
                raise ValidationError("A entrada não está mais em rascunho.")
            for item in locked.items.select_related("product"):
                product = Product.objects.select_for_update().get(pk=item.product_id)
                previous_stock = product.stock
                if item.unit_cost > 0:
                    new_total = previous_stock * product.cost_price + item.quantity * item.unit_cost
                    new_qty = previous_stock + item.quantity
                    product.cost_price = new_total / new_qty if new_qty else item.unit_cost
                    product.save(update_fields=["cost_price", "updated_at"])
                lot, _ = Lot.objects.select_for_update().get_or_create(
                    product=product,
                    number=item.lot_number or f"SEM-LOTE-{locked.number}-{item.pk}",
                    defaults={
                        "supplier": locked.supplier,
                        "manufacturing_date": item.manufacturing_date,
                        "expiration_date": item.expiration_date,
                        "entry_date": timezone.localdate(locked.entry_date),
                        "cost_price": item.unit_cost,
                    },
                )
                lot.supplier = locked.supplier
                lot.manufacturing_date = item.manufacturing_date or lot.manufacturing_date
                lot.expiration_date = item.expiration_date or lot.expiration_date
                lot.cost_price = item.unit_cost
                lot.received_quantity += item.quantity
                lot.save()
                item.lot = lot
                item.save(update_fields=["lot"])
                from .movement import Movement
                Movement.register(
                    product=product,
                    type=Movement.ENTRY,
                    quantity=item.quantity,
                    user=user or locked.user,
                    lot=lot,
                    reason="Entrada de estoque",
                    notes=item.notes or locked.notes,
                    unit_cost=item.unit_cost,
                    document=locked.number,
                    entry=locked,
                )
                ProductSupplier.objects.update_or_create(
                    product=product,
                    supplier=locked.supplier,
                    defaults={
                        "is_primary": product.supplier_id == locked.supplier_id,
                        "last_cost": item.unit_cost,
                    },
                )
            locked.recalculate_total()
            locked.status = self.CONFIRMED
            locked.confirmed_at = timezone.now()
            locked.save(update_fields=["status", "confirmed_at", "updated_at"])
            self.status = locked.status
            self.confirmed_at = locked.confirmed_at
            self.total_value = locked.total_value
        return self

    def cancel(self, user):
        if self.status != self.CONFIRMED:
            raise ValidationError("Somente entradas confirmadas podem ser canceladas.")
        with transaction.atomic():
            locked = StockEntry.objects.select_for_update().get(pk=self.pk)
            from .movement import Movement
            movements = locked.movements.filter(reversed=False).select_related("product", "lot")
            for original in movements:
                Movement.reverse(original=original, user=user, reason=f"Cancelamento da entrada {locked.number}")
            locked.status = self.CANCELLED
            locked.cancelled_at = timezone.now()
            locked.cancelled_by = user
            locked.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
            self.status = locked.status
        return self


class StockEntryItem(TimeStamped):
    entry = models.ForeignKey(StockEntry, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="entry_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    lot_number = models.CharField(max_length=80, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL, null=True, blank=True, related_name="entry_items")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0, unit_cost__gte=0), name="inv_entry_item_values_valid")
        ]

    @property
    def subtotal(self):
        return self.quantity * self.unit_cost


