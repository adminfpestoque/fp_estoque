from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument, TimeStamped
from .catalog import Lot, Product, ProductPackaging


class StockOutput(NumberedDocument):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    STATUSES = [(DRAFT, "Rascunho"), (CONFIRMED, "Confirmada"), (CANCELLED, "Cancelada")]

    PAYMENT_NONE = "NONE"
    PAYMENT_CASH = "CASH"
    PAYMENT_PIX = "PIX"
    PAYMENT_DEBIT = "DEBIT"
    PAYMENT_CREDIT = "CREDIT"
    PAYMENT_TRANSFER = "TRANSFER"
    PAYMENT_ON_ACCOUNT = "ON_ACCOUNT"
    PAYMENT_OTHER = "OTHER"
    PAYMENT_METHODS = [
        (PAYMENT_NONE, "Não se aplica"),
        (PAYMENT_CASH, "Dinheiro"),
        (PAYMENT_PIX, "Pix"),
        (PAYMENT_DEBIT, "Cartão de débito"),
        (PAYMENT_CREDIT, "Cartão de crédito"),
        (PAYMENT_TRANSFER, "Transferência"),
        (PAYMENT_ON_ACCOUNT, "A prazo/fiado"),
        (PAYMENT_OTHER, "Outro"),
    ]

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
    customer_name = models.CharField(max_length=160, blank=True)
    payment_method = models.CharField(
        max_length=16,
        choices=PAYMENT_METHODS,
        default=PAYMENT_NONE,
    )
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=100, blank=True)
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
        indexes = [
            models.Index(fields=["status", "output_date"], name="inv_output_status_date_idx"),
            models.Index(fields=["payment_method", "output_date"], name="inv_output_payment_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_value__gte=0, amount_received__gte=0),
                name="inv_output_payment_values_nonnegative",
            )
        ]

    def save(self, *args, **kwargs):
        self.ensure_number("SAI")
        super().save(*args, **kwargs)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_status(self):
        return "Excluída" if self.is_deleted else self.get_status_display()

    @property
    def change_amount(self):
        if self.payment_method != self.PAYMENT_CASH:
            return Decimal("0.00")
        return max(self.amount_received - self.total_value, Decimal("0.00"))

    def recalculate_total(self, save=True):
        total = sum((item.subtotal for item in self.items.all()), Decimal("0.00"))
        self.total_value = total.quantize(Decimal("0.01"))
        if self.reason != "COMMERCIAL":
            self.payment_method = self.PAYMENT_NONE
            self.amount_received = Decimal("0.00")
            self.payment_reference = ""
        elif self.payment_method not in {self.PAYMENT_NONE, self.PAYMENT_CASH}:
            self.amount_received = self.total_value
        if save:
            self.save(
                update_fields=[
                    "total_value",
                    "payment_method",
                    "amount_received",
                    "payment_reference",
                    "updated_at",
                ]
            )
        return self.total_value

    def validate_checkout(self, require_payment=True):
        if self.reason != "COMMERCIAL":
            return
        if self.payment_method == self.PAYMENT_NONE:
            if require_payment:
                raise ValidationError("Selecione a forma de pagamento para finalizar a venda.")
            self.payment_method = self.PAYMENT_OTHER
            self.amount_received = self.total_value
            self.save(update_fields=["payment_method", "amount_received", "updated_at"])
        if self.total_value <= 0:
            raise ValidationError("O total da venda deve ser maior que zero.")
        if self.payment_method == self.PAYMENT_CASH and self.amount_received < self.total_value:
            missing = self.total_value - self.amount_received
            raise ValidationError(
                f"O valor recebido é insuficiente. Faltam R$ {missing:.2f}."
            )

    def confirm(self, user=None, require_payment=False):
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
            locked.recalculate_total()
            locked.validate_checkout(require_payment=require_payment)

            items = list(
                locked.items.select_related("product", "lot", "packaging").order_by("pk")
            )
            for item in items:
                if not item.product_id:
                    raise ValidationError("Um item da saída está sem produto vinculado.")
                product = Product.objects.select_for_update().get(pk=item.product_id)
                if product.deleted_at or not product.active:
                    raise ValidationError(
                        f"O produto {product.name} está inativo ou excluído e não pode ser retirado."
                    )
                if product.stock < item.quantity:
                    raise ValidationError(f"Estoque insuficiente para {product.name}.")
                from .movement import Movement

                Movement.consume_fefo(
                    product=product,
                    quantity=item.quantity,
                    user=user or locked.user,
                    preferred_lot=item.lot,
                    reason=locked.get_reason_display(),
                    notes=item.notes or locked.notes,
                    document=locked.number,
                    output=locked,
                    unit_sale_price=item.unit_sale_price,
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
            self.total_value = locked.total_value
            self.amount_received = locked.amount_received
            self.payment_method = locked.payment_method
        return self

    def cancel(self, user):
        if self.is_deleted:
            raise ValidationError("Esta saída já está excluída.")
        if self.status != self.CONFIRMED:
            raise ValidationError("Somente saídas confirmadas podem ser canceladas.")
        with transaction.atomic():
            from .movement import Movement

            locked = StockOutput.objects.select_for_update().get(pk=self.pk)
            if locked.status != self.CONFIRMED:
                raise ValidationError("A saída não está mais disponível para cancelamento.")
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
    packaging = models.ForeignKey(
        ProductPackaging,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="output_items",
    )
    sale_unit_name = models.CharField(max_length=50, default="Unidade")
    sale_quantity = models.PositiveIntegerField(default=1)
    conversion_factor = models.PositiveIntegerField(default=1)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="output_items")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=0,
                    sale_quantity__gt=0,
                    conversion_factor__gt=0,
                    unit_sale_price__gte=0,
                    sale_price__gte=0,
                ),
                name="inv_output_item_values_valid",
            )
        ]

    def save(self, *args, **kwargs):
        if (
            self._state.adding
            and not self.packaging_id
            and self.sale_quantity == 1
            and self.quantity
            and Decimal(self.quantity) > 1
        ):
            # Compatibilidade com registros internos antigos que informavam
            # diretamente a quantidade em unidades.
            self.sale_quantity = int(Decimal(self.quantity))
        if self.product_id:
            self.product_name_snapshot = self.product.name
            self.product_code_snapshot = self.product.code
        if self.packaging_id:
            self.sale_unit_name = self.packaging.display_name
            self.conversion_factor = self.packaging.units_per_package
            if not self.sale_price:
                if self.unit_sale_price:
                    # Compatibilidade: o preço antigo era informado por unidade individual.
                    self.sale_price = (
                        Decimal(self.unit_sale_price) * Decimal(self.conversion_factor)
                    ).quantize(Decimal("0.01"))
                else:
                    self.sale_price = self.packaging.sale_price
        else:
            self.sale_unit_name = "Unidade"
            self.conversion_factor = 1
            if not self.sale_price:
                if self.unit_sale_price:
                    self.sale_price = Decimal(self.unit_sale_price)
                elif self.product_id:
                    self.sale_price = self.product.sale_price
        self.quantity = Decimal(self.sale_quantity) * Decimal(self.conversion_factor)
        self.unit_sale_price = (
            Decimal(self.sale_price) / Decimal(self.conversion_factor)
            if self.conversion_factor
            else Decimal(self.sale_price)
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
        return Decimal(self.sale_quantity) * Decimal(self.sale_price)

    @property
    def sale_unit_description(self):
        if self.conversion_factor == 1:
            return "Unidade"
        return f"{self.sale_unit_name} ({self.conversion_factor} unidades)"
