from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument, TimeStamped
from .catalog import Lot, Product, ProductPackaging, ProductSupplier, Supplier


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
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deleted_entries",
    )
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [models.Index(fields=["status", "entry_date"], name="inv_entry_status_date_idx")]

    def save(self, *args, **kwargs):
        self.ensure_number("ENT")
        super().save(*args, **kwargs)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_status(self):
        return "Excluída" if self.is_deleted else self.get_status_display()

    def recalculate_total(self):
        total = sum((item.subtotal for item in self.items.all()), Decimal("0"))
        self.total_value = total
        self.save(update_fields=["total_value", "updated_at"])

    def confirm(self, user=None):
        if self.is_deleted:
            raise ValidationError("Uma entrada excluída não pode ser confirmada.")
        if self.status == self.CONFIRMED:
            raise ValidationError("Esta entrada já foi confirmada.")
        if self.status == self.CANCELLED:
            raise ValidationError("Uma entrada cancelada não pode ser confirmada.")
        if not self.items.exists():
            raise ValidationError("Inclua ao menos um item antes de confirmar.")

        with transaction.atomic():
            locked = StockEntry.objects.select_for_update().get(pk=self.pk)
            if locked.status != self.DRAFT or locked.deleted_at:
                raise ValidationError("A entrada não está mais disponível para confirmação.")
            for item in locked.items.select_related("product"):
                if not item.product_id:
                    raise ValidationError("Um item da entrada está sem produto vinculado.")
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
                lot.active = True
                lot.save()
                item.lot = lot
                item.save(update_fields=["lot", "updated_at"])
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
                if item.packaging_id and item.purchase_price > 0:
                    packaging = ProductPackaging.objects.select_for_update().get(pk=item.packaging_id)
                    packaging.cost_price = item.purchase_price
                    packaging.save(update_fields=["cost_price", "updated_at"])
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
            self.total_value = locked.total_value
        return self

    def cancel(self, user):
        if self.is_deleted:
            raise ValidationError("Esta entrada já está excluída.")
        if self.status != self.CONFIRMED:
            raise ValidationError("Somente entradas confirmadas podem ser canceladas.")
        with transaction.atomic():
            locked = StockEntry.objects.select_for_update().get(pk=self.pk)
            from .movement import Movement

            movements = list(
                locked.movements.filter(reversed=False).select_related("product", "lot")
            )
            for original in movements:
                Movement.reverse(
                    original=original,
                    user=user,
                    reason=f"Cancelamento da entrada {locked.number}",
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
            raise ValidationError("Esta entrada já foi excluída.")
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


class StockEntryItem(TimeStamped):
    entry = models.ForeignKey(StockEntry, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_items",
    )
    product_name_snapshot = models.CharField(max_length=180, blank=True)
    product_code_snapshot = models.CharField(max_length=50, blank=True)
    packaging = models.ForeignKey(
        ProductPackaging,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_items",
    )
    entry_unit_name = models.CharField(max_length=60, default="Unidade")
    entry_quantity = models.PositiveIntegerField(default=1)
    conversion_factor = models.PositiveIntegerField(default=1)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Quantidade e custo por unidade real de estoque.
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    lot_number = models.CharField(max_length=80, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL, null=True, blank=True, related_name="entry_items")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=0,
                    unit_cost__gte=0,
                    entry_quantity__gt=0,
                    conversion_factor__gt=0,
                    purchase_price__gte=0,
                ),
                name="inv_entry_item_packaging_values_valid",
            )
        ]

    def save(self, *args, **kwargs):
        if (
            self._state.adding
            and not self.packaging_id
            and self.entry_quantity == 1
            and self.quantity
            and Decimal(self.quantity) > 1
        ):
            self.entry_quantity = int(Decimal(self.quantity))
            if not self.purchase_price:
                self.purchase_price = self.unit_cost
        if self.product_id:
            self.product_name_snapshot = self.product.name
            self.product_code_snapshot = self.product.code
        if self.packaging_id:
            self.entry_unit_name = self.packaging.display_name
            self.conversion_factor = self.packaging.units_per_package
            if not self.purchase_price:
                if self.unit_cost:
                    # Compatibilidade: custo antigo era informado por unidade individual.
                    self.purchase_price = (
                        Decimal(self.unit_cost) * Decimal(self.conversion_factor)
                    ).quantize(Decimal("0.01"))
                else:
                    self.purchase_price = self.packaging.cost_price
        else:
            self.entry_unit_name = "Unidade"
            self.conversion_factor = 1
            if not self.purchase_price:
                if self.unit_cost:
                    self.purchase_price = Decimal(self.unit_cost)
                elif self.product_id:
                    self.purchase_price = self.product.cost_price
        self.quantity = Decimal(self.entry_quantity) * Decimal(self.conversion_factor)
        self.unit_cost = (
            Decimal(self.purchase_price) / Decimal(self.conversion_factor)
            if self.conversion_factor
            else Decimal(self.purchase_price)
        ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    @property
    def product_name(self):
        return self.product.name if self.product_id else self.product_name_snapshot

    @property
    def product_code(self):
        return self.product.code if self.product_id else self.product_code_snapshot

    @property
    def subtotal(self):
        return Decimal(self.entry_quantity) * Decimal(self.purchase_price)

    @property
    def entry_unit_description(self):
        if self.conversion_factor == 1:
            return "Unidade"
        return f"{self.entry_unit_name} ({self.conversion_factor} unidades)"

