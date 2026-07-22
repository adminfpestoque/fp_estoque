from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone

from ..models import InventoryItem, Lot, Movement, Product, SystemSetting
from .common import decimal_text, filters_used, money, movement_queryset, reconstruct_stock_at
from .constants import REPORT_TYPES


def daily_data(params, user):
    qs, period = movement_queryset(params)
    start, end, _, end_dt = period
    entries = qs.filter(type=Movement.ENTRY)
    outputs = qs.filter(type__in=[Movement.OUTPUT, Movement.TRANSFER, Movement.LOSS, Movement.DAMAGE, Movement.EXPIRED])
    adj_pos = qs.filter(type__in=[Movement.ADJUSTMENT_IN, Movement.INVENTORY])
    adj_neg = qs.filter(type=Movement.ADJUSTMENT_OUT)

    products_moved = qs.values("product_id").distinct().count()
    entry_value = entries.aggregate(v=Sum(F("quantity") * F("unit_cost")))["v"] or 0
    output_value = outputs.aggregate(v=Sum(F("quantity") * F("unit_cost")))["v"] or 0
    end_value = Decimal("0")
    low_products = []
    empty_products = []
    for product in Product.objects.filter(active=True).select_related("category"):
        final_stock = reconstruct_stock_at(product, end_dt)
        end_value += final_stock * product.cost_price
        if final_stock <= 0:
            empty_products.append(product)
        elif final_stock <= product.minimum_stock:
            low_products.append(product)

    expiry_days = SystemSetting.get_int("expiration_alert_days", 30)
    expiry_limit = end + timedelta(days=expiry_days)
    expiring_lots = Lot.objects.select_related("product").filter(
        quantity__gt=0, expiration_date__gte=end, expiration_date__lte=expiry_limit
    )
    expired_lots = Lot.objects.select_related("product").filter(quantity__gt=0, expiration_date__lt=end)
    divergences = InventoryItem.objects.select_related("inventory", "product").filter(
        inventory__started_at__date__range=(start, end)
    ).exclude(system_quantity=F("counted_quantity"))

    rows = []
    for movement in qs:
        rows.append({
            "time": timezone.localtime(movement.created_at).strftime("%d/%m/%Y %H:%M"),
            "type": movement.get_type_display(),
            "product": movement.product.name,
            "code": movement.product.code,
            "category": movement.product.category.name,
            "lot": movement.lot.number if movement.lot else "-",
            "previous": decimal_text(movement.previous_stock),
            "quantity": decimal_text(movement.quantity),
            "final": decimal_text(movement.final_stock),
            "unit_cost": money(movement.unit_cost),
            "total": money(movement.total_value),
            "reason": movement.reason or "-",
            "document": movement.document or "-",
            "user": movement.user.get_full_name() or movement.user.username,
            "notes": movement.notes or "-",
            "reversed": movement.reversed,
        })

    summary = {
        "total_movements": qs.count(),
        "entries": entries.count(),
        "outputs": outputs.count(),
        "adjustments_positive": adj_pos.count(),
        "adjustments_negative": adj_neg.count(),
        "products_moved": products_moved,
        "entry_value": money(entry_value),
        "output_value": money(output_value),
        "end_inventory_value": money(end_value),
        "cancelled_or_reversed": qs.filter(Q(reversed=True) | Q(type__in=[Movement.REVERSAL_IN, Movement.REVERSAL_OUT])).count(),
    }
    sections = {
        "entries": [row for row in rows if row["type"] == "Entrada"],
        "outputs": [row for row in rows if row["type"] in ["Saída", "Transferência", "Perda", "Avaria", "Produto vencido"]],
        "adjustments": [row for row in rows if "Ajuste" in row["type"] or row["type"] == "Inventário"],
        "reversals": [row for row in rows if "Estorno" in row["type"] or row["reversed"]],
        "divergences": [
            {
                "inventory": item.inventory.number,
                "product": item.product.name,
                "system": decimal_text(item.system_quantity),
                "counted": decimal_text(item.counted_quantity),
                "difference": decimal_text(item.difference),
                "justification": item.justification or "-",
            }
            for item in divergences
        ],
        "alerts": {
            "low_stock": [{"product": p.name, "stock": decimal_text(reconstruct_stock_at(p, end_dt)), "minimum": decimal_text(p.minimum_stock)} for p in low_products],
            "out_of_stock": [{"product": p.name, "stock": "0"} for p in empty_products],
            "expiring": [{"product": lot.product.name, "lot": lot.number, "expiration": lot.expiration_date.strftime("%d/%m/%Y"), "quantity": decimal_text(lot.quantity)} for lot in expiring_lots],
            "expired": [{"product": lot.product.name, "lot": lot.number, "expiration": lot.expiration_date.strftime("%d/%m/%Y"), "quantity": decimal_text(lot.quantity)} for lot in expired_lots],
        },
    }
    return {
        "report_type": "daily_movements",
        "title": REPORT_TYPES["daily_movements"],
        "period": f"{start.strftime('%d/%m/%Y')}" if start == end else f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        "generated_by": user.get_full_name() or user.username,
        "filters": filters_used(params),
        "summary": summary,
        "columns": ["Horário", "Tipo", "Produto", "Código", "Categoria", "Lote", "Qtd. anterior", "Movimentada", "Qtd. final", "Custo", "Valor total", "Motivo", "Documento", "Usuário", "Observações"],
        "rows": rows,
        "sections": sections,
        "empty_message": "Não houve movimentações no período selecionado." if not rows else "",
    }
