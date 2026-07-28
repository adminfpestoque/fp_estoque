from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .catalog import Lot, Product, ProductPackaging, ProductSupplier
from .entry import StockEntry, StockEntryItem
from .movement import Movement


if not getattr(Movement, "_entry_reversal_consistency_installed", False):
    _original_reverse = Movement.reverse.__func__

    @classmethod
    def reverse_with_entry_consistency(cls, *, original, user, reason=""):
        if original.type != cls.ENTRY:
            return _original_reverse(
                cls,
                original=original,
                user=user,
                reason=reason,
            )

        if original.reversed:
            raise ValidationError("Esta movimentação já foi estornada.")
        if not original.product_id:
            raise ValidationError(
                "O produto desta movimentação foi excluído e não pode mais ser estornado."
            )

        with transaction.atomic():
            original = (
                cls.objects.select_for_update()
                .select_related("product", "lot")
                .get(pk=original.pk)
            )
            if original.reversed:
                raise ValidationError("Esta movimentação já foi estornada.")

            product = Product.objects.select_for_update().get(pk=original.product_id)
            if product.stock < original.quantity:
                raise ValidationError(
                    "Não há estoque suficiente para estornar esta entrada."
                )

            remaining_stock = product.stock - original.quantity
            remaining_value = (
                product.stock * product.cost_price
                - original.quantity * original.unit_cost
            )
            if remaining_value < 0:
                remaining_value = Decimal("0")

            new_cost = Decimal("0")
            if remaining_stock > 0:
                new_cost = (remaining_value / remaining_stock).quantize(
                    Decimal("0.01")
                )

            movement = cls.register(
                product=product,
                type=cls.REVERSAL_OUT,
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

            product.refresh_from_db(fields=["stock", "cost_price", "updated_at"])
            product.cost_price = new_cost
            product.save(update_fields=["cost_price", "updated_at"])

            if original.lot_id:
                lot = Lot.objects.select_for_update().get(pk=original.lot_id)
                lot.received_quantity = max(
                    Decimal("0"),
                    lot.received_quantity - original.quantity,
                )
                if lot.quantity <= 0 and lot.received_quantity <= 0:
                    lot.active = False
                lot.save(
                    update_fields=[
                        "received_quantity",
                        "active",
                        "updated_at",
                    ]
                )

            original.reversed = True
            original.save(update_fields=["reversed", "updated_at"])
            return movement

    Movement.reverse = reverse_with_entry_consistency
    Movement._entry_reversal_consistency_installed = True


if not getattr(StockEntry, "_cost_reference_consistency_installed", False):
    _original_cancel = StockEntry.cancel

    def _latest_confirmed_item(*, product_id, supplier_id=None, packaging_id=None):
        queryset = StockEntryItem.objects.filter(
            product_id=product_id,
            entry__status=StockEntry.CONFIRMED,
            entry__deleted_at__isnull=True,
        )
        if supplier_id is not None:
            queryset = queryset.filter(entry__supplier_id=supplier_id)
        if packaging_id is not None:
            queryset = queryset.filter(packaging_id=packaging_id)
        return (
            queryset.select_related("entry")
            .order_by("-entry__confirmed_at", "-entry__entry_date", "-pk")
            .first()
        )

    def cancel_with_reference_recalculation(self, user):
        affected_items = list(
            self.items.select_related("product", "packaging").all()
        )
        supplier_id = self.supplier_id

        with transaction.atomic():
            result = _original_cancel(self, user)

            packaging_ids = {
                item.packaging_id
                for item in affected_items
                if item.packaging_id
            }
            product_ids = {
                item.product_id
                for item in affected_items
                if item.product_id
            }

            for packaging_id in packaging_ids:
                packaging = ProductPackaging.objects.select_for_update().get(
                    pk=packaging_id
                )
                latest = _latest_confirmed_item(
                    product_id=packaging.product_id,
                    packaging_id=packaging_id,
                )
                packaging.cost_price = (
                    latest.purchase_price if latest else Decimal("0")
                )
                packaging.save(update_fields=["cost_price", "updated_at"])

            for product_id in product_ids:
                link = ProductSupplier.objects.filter(
                    product_id=product_id,
                    supplier_id=supplier_id,
                ).first()
                if not link:
                    continue
                latest = _latest_confirmed_item(
                    product_id=product_id,
                    supplier_id=supplier_id,
                )
                link.last_cost = latest.unit_cost if latest else Decimal("0")
                link.save(update_fields=["last_cost", "updated_at"])

            return result

    StockEntry.cancel = cancel_with_reference_recalculation
    StockEntry._cost_reference_consistency_installed = True
