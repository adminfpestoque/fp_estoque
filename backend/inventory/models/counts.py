from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .base import NumberedDocument, TimeStamped
from .catalog import Category, Product
from .movement import Movement


class InventoryCount(NumberedDocument):
    OPEN = "OPEN"
    WAITING = "WAITING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    STATUS = [
        (OPEN, "Em andamento"),
        (WAITING, "Aguardando confirmação"),
        (DONE, "Concluído"),
        (CANCELLED, "Cancelado"),
    ]

    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=OPEN)
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventories",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventories",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_inventories",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="completed_inventories",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_inventories",
    )

    class Meta:
        ordering = ["-started_at"]

    def save(self, *args, **kwargs):
        self.ensure_number("INV")
        super().save(*args, **kwargs)

    def validate_ready(self):
        items = list(self.items.select_related("product", "counted_by"))
        if not items:
            raise ValidationError("O inventário não possui produtos para conferência.")

        pending = [item.product.name for item in items if not item.counted]
        if pending:
            preview = ", ".join(pending[:5])
            suffix = "..." if len(pending) > 5 else ""
            raise ValidationError(
                f"Ainda existem {len(pending)} produto(s) sem contagem: {preview}{suffix}"
            )

        without_justification = [
            item.product.name
            for item in items
            if item.difference != 0 and not item.justification.strip()
        ]
        if without_justification:
            preview = ", ".join(without_justification[:5])
            suffix = "..." if len(without_justification) > 5 else ""
            raise ValidationError(
                "Informe uma justificativa para todas as divergências: "
                f"{preview}{suffix}"
            )
        return items

    def submit(self, user):
        if self.status != self.OPEN:
            raise ValidationError("Somente inventários em andamento podem ser enviados.")
        self.validate_ready()
        self.status = self.WAITING
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.save(
            update_fields=[
                "status",
                "submitted_at",
                "submitted_by",
                "updated_at",
            ]
        )
        return self

    def reopen(self):
        if self.status != self.WAITING:
            raise ValidationError("Somente inventários aguardando confirmação podem ser reabertos.")
        self.status = self.OPEN
        self.submitted_at = None
        self.submitted_by = None
        self.save(
            update_fields=[
                "status",
                "submitted_at",
                "submitted_by",
                "updated_at",
            ]
        )
        return self

    def cancel(self, user, reason=""):
        if self.status == self.DONE:
            raise ValidationError("Inventário concluído não pode ser cancelado.")
        if self.status == self.CANCELLED:
            raise ValidationError("Este inventário já foi cancelado.")
        self.status = self.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = reason.strip()
        self.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )
        return self

    def conclude(self, user):
        if self.status == self.OPEN:
            self.submit(user)
        elif self.status != self.WAITING:
            raise ValidationError(
                "O inventário precisa estar aguardando confirmação para ser concluído."
            )

        with transaction.atomic():
            items = self.validate_ready()
            stale_products = []
            for item in items:
                if item.counted_at and Movement.objects.filter(
                    product=item.product,
                    created_at__gt=item.counted_at,
                ).exists():
                    stale_products.append(item.product.name)

            if stale_products:
                preview = ", ".join(stale_products[:5])
                suffix = "..." if len(stale_products) > 5 else ""
                raise ValidationError(
                    "Houve movimentação após a contagem dos seguintes produtos: "
                    f"{preview}{suffix}. Reabra o inventário e refaça essas contagens."
                )

            for item in items:
                product = Product.objects.select_for_update().get(pk=item.product_id)
                adjustment = item.counted_quantity - product.stock
                if adjustment:
                    movement = Movement.register(
                        product=product,
                        type=(
                            Movement.ADJUSTMENT_IN
                            if adjustment > 0
                            else Movement.ADJUSTMENT_OUT
                        ),
                        quantity=abs(adjustment),
                        user=user,
                        reason=f"Divergência do inventário {self.number}",
                        notes=item.justification,
                        document=self.number,
                    )
                    item.adjustment_movement = movement
                    item.adjusted = True
                    item.save(
                        update_fields=[
                            "adjustment_movement",
                            "adjusted",
                            "updated_at",
                        ]
                    )

            self.status = self.DONE
            self.completed_at = timezone.now()
            self.completed_by = user
            self.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "completed_by",
                    "updated_at",
                ]
            )
        return self


class InventoryItem(TimeStamped):
    inventory = models.ForeignKey(
        InventoryCount,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    system_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    counted_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    counted = models.BooleanField(default=True)
    counted_at = models.DateTimeField(null=True, blank=True)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_item_counts",
    )
    justification = models.TextField(blank=True)
    adjusted = models.BooleanField(default=False)
    adjustment_movement = models.OneToOneField(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_item",
    )

    class Meta:
        ordering = ["product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "product"],
                name="inventory_inventoryitem_inventory_product_uniq",
            ),
            models.CheckConstraint(
                condition=Q(system_quantity__gte=0, counted_quantity__gte=0),
                name="inventory_inventoryitem_quantities_nonnegative",
            ),
        ]

    @property
    def difference(self):
        return self.counted_quantity - self.system_quantity

    @property
    def adjustment_value(self):
        return self.difference * self.product.cost_price
