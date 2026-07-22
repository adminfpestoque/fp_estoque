from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q

from .base import TimeStamped
from .catalog import Lot, Product


class Movement(TimeStamped):
    ENTRY = "ENTRY"
    OUTPUT = "OUTPUT"
    ADJUSTMENT_IN = "ADJ_IN"
    ADJUSTMENT_OUT = "ADJ_OUT"
    TRANSFER = "TRANSFER"
    LOSS = "LOSS"
    DAMAGE = "DAMAGE"
    EXPIRED = "EXPIRED"
    REVERSAL_IN = "REV_IN"
    REVERSAL_OUT = "REV_OUT"
    INVENTORY = "INVENTORY"
    TYPES = [
        (ENTRY, "Entrada"),
        (OUTPUT, "Saída"),
        (ADJUSTMENT_IN, "Ajuste positivo"),
        (ADJUSTMENT_OUT, "Ajuste negativo"),
        (TRANSFER, "Transferência"),
        (LOSS, "Perda"),
        (DAMAGE, "Avaria"),
        (EXPIRED, "Produto vencido"),
        (REVERSAL_IN, "Estorno positivo"),
        (REVERSAL_OUT, "Estorno negativo"),
        (INVENTORY, "Inventário"),
    ]
    INCREASE_TYPES = {ENTRY, ADJUSTMENT_IN, REVERSAL_IN, INVENTORY}
    DECREASE_TYPES = {OUTPUT, ADJUSTMENT_OUT, TRANSFER, LOSS, DAMAGE, EXPIRED, REVERSAL_OUT}

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements")
    type = models.CharField(max_length=16, choices=TYPES)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    previous_stock = models.DecimalField(max_digits=14, decimal_places=3)
    final_stock = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.CharField(max_length=200, blank=True)
    document = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements")
    reversed = models.BooleanField(default=False)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")
    entry = models.ForeignKey("inventory.StockEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="movements")
    output = models.ForeignKey("inventory.StockOutput", on_delete=models.PROTECT, null=True, blank=True, related_name="movements")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="inv_movement_created_idx"),
            models.Index(fields=["type"], name="inv_movement_type_idx"),
            models.Index(fields=["product", "created_at"], name="inv_mov_prod_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0, previous_stock__gte=0, final_stock__gte=0, unit_cost__gte=0),
                name="inventory_movement_quantities_valid",
            )
        ]

    @property
    def total_value(self):
        return self.quantity * self.unit_cost

    @property
    def sale_value(self):
        return self.quantity * self.unit_sale_price

    @property
    def gross_profit(self):
        return self.sale_value - self.total_value

    @classmethod
    def register(
        cls,
        *,
        product,
        type,
        quantity,
        user,
        lot=None,
        reason="",
        document="",
        notes="",
        unit_cost=None,
        unit_sale_price=None,
        entry=None,
        output=None,
        reversal_of=None,
    ):
        if type not in dict(cls.TYPES):
            raise ValidationError("Tipo de movimentação inválido.")
        quantity = Decimal(str(quantity)).copy_abs()
        if quantity <= 0:
            raise ValidationError("A quantidade deve ser maior que zero.")

        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product.pk)
            previous = product.stock
            is_increase = type in cls.INCREASE_TYPES
            delta = quantity if is_increase else -quantity
            if previous + delta < 0:
                raise ValidationError("Estoque insuficiente para esta movimentação.")

            if lot:
                lot = Lot.objects.select_for_update().get(pk=lot.pk)
                if lot.product_id != product.pk:
                    raise ValidationError("O lote não pertence ao produto selecionado.")
                if lot.quantity + delta < 0:
                    raise ValidationError("Quantidade insuficiente no lote.")
                lot.quantity = F("quantity") + delta
                lot.save(update_fields=["quantity", "updated_at"])
                lot.refresh_from_db(fields=["quantity", "updated_at"])

            product.stock = previous + delta
            product.save(update_fields=["stock", "updated_at"])
            sale_price = unit_sale_price
            if sale_price is None:
                sale_price = product.sale_price if type == cls.OUTPUT else Decimal("0")
            return cls.objects.create(
                product=product,
                lot=lot,
                type=type,
                quantity=quantity,
                previous_stock=previous,
                final_stock=product.stock,
                unit_cost=unit_cost if unit_cost is not None else product.cost_price,
                unit_sale_price=sale_price,
                reason=reason,
                document=document,
                notes=notes,
                user=user,
                entry=entry,
                output=output,
                reversal_of=reversal_of,
            )

    @classmethod
    def consume_fefo(
        cls,
        *,
        product,
        quantity,
        user,
        preferred_lot=None,
        reason="",
        notes="",
        document="",
        output=None,
        unit_sale_price=None,
    ):
        remaining = Decimal(str(quantity))
        movements = []
        if preferred_lot:
            if preferred_lot.product_id != product.pk:
                raise ValidationError("O lote selecionado não pertence ao produto.")
            if preferred_lot.quantity < remaining:
                raise ValidationError("Quantidade insuficiente no lote selecionado.")
            return [
                cls.register(
                    product=product,
                    type=cls.OUTPUT,
                    quantity=remaining,
                    user=user,
                    lot=preferred_lot,
                    reason=reason,
                    notes=notes,
                    document=document,
                    output=output,
                    unit_sale_price=unit_sale_price,
                )
            ]

        lots = list(
            Lot.objects.select_for_update()
            .filter(product=product, active=True, quantity__gt=0)
            .order_by(F("expiration_date").asc(nulls_last=True), "entry_date", "created_at")
        )
        for lot in lots:
            if remaining <= 0:
                break
            take = min(remaining, lot.quantity)
            movements.append(
                cls.register(
                    product=product,
                    type=cls.OUTPUT,
                    quantity=take,
                    user=user,
                    lot=lot,
                    reason=reason,
                    notes=notes,
                    document=document,
                    output=output,
                    unit_sale_price=unit_sale_price,
                )
            )
            remaining -= take
        if remaining > 0:
            refreshed = Product.objects.get(pk=product.pk)
            if refreshed.stock < remaining:
                raise ValidationError("Estoque insuficiente para esta saída.")
            movements.append(
                cls.register(
                    product=refreshed,
                    type=cls.OUTPUT,
                    quantity=remaining,
                    user=user,
                    reason=reason,
                    notes=notes,
                    document=document,
                    output=output,
                    unit_sale_price=unit_sale_price,
                )
            )
        return movements

    @classmethod
    def reverse(cls, *, original, user, reason=""):
        if original.reversed:
            raise ValidationError("Esta movimentação já foi estornada.")
        reverse_type = cls.REVERSAL_OUT if original.type in cls.INCREASE_TYPES else cls.REVERSAL_IN
        with transaction.atomic():
            original = cls.objects.select_for_update().get(pk=original.pk)
            movement = cls.register(
                product=original.product,
                type=reverse_type,
                quantity=original.quantity,
                user=user,
                lot=original.lot,
                reason=reason or f"Estorno da movimentação #{original.pk}",
                document=original.document,
                notes=original.notes,
                unit_cost=original.unit_cost,
                unit_sale_price=original.unit_sale_price,
                reversal_of=original,
            )
            original.reversed = True
            original.save(update_fields=["reversed", "updated_at"])
            return movement
