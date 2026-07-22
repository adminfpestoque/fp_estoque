from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from ..models import InventoryItem, Lot, Product, StockEntry, StockOutput, SystemSetting
from .common import decimal_text, filters_used, money, movement_queryset, report_period
from .constants import REPORT_TYPES
from .daily import daily_data


def generic_report_data(report_type, params, user):
    start, end, start_dt, end_dt = report_period(params)
    title = REPORT_TYPES.get(report_type)
    if not title:
        raise ValueError("Tipo de relatório inválido.")

    columns, rows, summary = [], [], {}
    product_filters = {}
    if params.get("product"):
        product_filters["id"] = params["product"]
    if params.get("category"):
        product_filters["category_id"] = params["category"]
    if params.get("supplier"):
        product_filters["supplier_id"] = params["supplier"]
    products = Product.objects.select_related("category", "supplier").filter(**product_filters)

    if report_type in {"current_stock", "product_quantity", "low_stock", "out_of_stock", "inventory_value", "low_movement"}:
        if report_type == "low_stock":
            products = products.filter(stock__lte=F("minimum_stock"), stock__gt=0)
        elif report_type == "out_of_stock":
            products = products.filter(stock=0)
        elif report_type == "low_movement":
            days = int(params.get("days") or 30)
            cutoff = timezone.now() - timedelta(days=days)
            products = products.annotate(last_movement=Max("movements__created_at")).filter(Q(last_movement__lt=cutoff) | Q(last_movement__isnull=True))
        columns = ["Código", "Produto", "Categoria", "Marca", "Estoque", "Mínimo", "Máximo", "Custo", "Valor", "Situação"]
        for product in products.order_by("name"):
            situation = "Sem estoque" if product.stock <= 0 else "Estoque baixo" if product.low_stock else "Normal"
            rows.append([product.code, product.name, product.category.name, product.brand or "-", decimal_text(product.stock), decimal_text(product.minimum_stock), decimal_text(product.maximum_stock), money(product.cost_price), money(product.stock_value), situation])
        summary = {
            "products": len(rows),
            "total_quantity": decimal_text(sum((product.stock for product in products), Decimal("0"))),
            "total_value": money(sum((product.stock_value for product in products), Decimal("0"))),
        }

    elif report_type in {"lot_quantity", "expiring", "expired"}:
        lots = Lot.objects.select_related("product", "supplier").filter(quantity__gt=0)
        if params.get("product"):
            lots = lots.filter(product_id=params["product"])
        if params.get("supplier"):
            lots = lots.filter(supplier_id=params["supplier"])
        if report_type == "expiring":
            days = int(params.get("days") or SystemSetting.get_int("expiration_alert_days", 30))
            lots = lots.filter(expiration_date__gte=timezone.localdate(), expiration_date__lte=timezone.localdate() + timedelta(days=days))
        elif report_type == "expired":
            lots = lots.filter(expiration_date__lt=timezone.localdate())
        columns = ["Produto", "Código", "Lote", "Fornecedor", "Quantidade", "Entrada", "Fabricação", "Validade", "Custo", "Situação"]
        for lot in lots.order_by(F("expiration_date").asc(nulls_last=True), "product__name"):
            rows.append([lot.product.name, lot.product.code, lot.number, lot.supplier.name if lot.supplier else "-", decimal_text(lot.quantity), lot.entry_date.strftime("%d/%m/%Y"), lot.manufacturing_date.strftime("%d/%m/%Y") if lot.manufacturing_date else "-", lot.expiration_date.strftime("%d/%m/%Y") if lot.expiration_date else "-", money(lot.cost_price), lot.status])
        summary = {"lots": len(rows), "total_quantity": decimal_text(sum((lot.quantity for lot in lots), Decimal("0")))}

    elif report_type in {"entries", "entries_by_supplier"}:
        entries = StockEntry.objects.select_related("supplier", "user").filter(entry_date__range=(start_dt, end_dt))
        if params.get("supplier"):
            entries = entries.filter(supplier_id=params["supplier"])
        columns = ["Número", "Data", "Fornecedor", "Nota fiscal", "Itens", "Valor total", "Situação", "Responsável", "Observações"]
        for entry in entries.annotate(items_count=Count("items")):
            rows.append([entry.number, timezone.localtime(entry.entry_date).strftime("%d/%m/%Y %H:%M"), entry.supplier.name, entry.invoice_number or "-", entry.items_count, money(entry.total_value), entry.get_status_display(), entry.user.get_full_name() or entry.user.username, entry.notes or "-"])
        summary = {"entries": len(rows), "total_value": money(entries.aggregate(v=Sum("total_value"))["v"] or 0)}

    elif report_type == "outputs":
        outputs = StockOutput.objects.select_related("user").filter(output_date__range=(start_dt, end_dt))
        columns = ["Número", "Data", "Motivo", "Itens", "Situação", "Responsável", "Observações"]
        for output in outputs.annotate(items_count=Count("items")):
            rows.append([output.number, timezone.localtime(output.output_date).strftime("%d/%m/%Y %H:%M"), output.get_reason_display(), output.items_count, output.get_status_display(), output.user.get_full_name() or output.user.username, output.notes or "-"])
        summary = {"outputs": len(rows)}

    elif report_type in {"movement_history", "movements_by_user", "movements_by_product"}:
        movements, _ = movement_queryset(params)
        columns = ["Data/hora", "Tipo", "Produto", "Código", "Lote", "Anterior", "Quantidade", "Final", "Valor", "Usuário", "Documento", "Motivo"]
        for movement in movements:
            rows.append([timezone.localtime(movement.created_at).strftime("%d/%m/%Y %H:%M"), movement.get_type_display(), movement.product.name, movement.product.code, movement.lot.number if movement.lot else "-", decimal_text(movement.previous_stock), decimal_text(movement.quantity), decimal_text(movement.final_stock), money(movement.total_value), movement.user.get_full_name() or movement.user.username, movement.document or "-", movement.reason or "-"])
        summary = {"movements": len(rows), "total_value": money(sum((movement.total_value for movement in movements), Decimal("0")))}

    elif report_type == "inventory_value_category":
        categories = products.values("category__name").annotate(quantity=Coalesce(Sum("stock"), Decimal("0")), value=Coalesce(Sum(F("stock") * F("cost_price")), Decimal("0"))).order_by("category__name")
        columns = ["Categoria", "Quantidade", "Valor estimado"]
        for item in categories:
            rows.append([item["category__name"], decimal_text(item["quantity"]), money(item["value"])])
        summary = {"categories": len(rows), "total_value": money(sum((Decimal(item["value"]) for item in categories), Decimal("0")))}

    elif report_type == "inventory_divergences":
        items = InventoryItem.objects.select_related("inventory", "product", "inventory__user").filter(inventory__started_at__range=(start_dt, end_dt)).exclude(system_quantity=F("counted_quantity"))
        columns = ["Inventário", "Data", "Produto", "Registrado", "Contado", "Divergência", "Ajustado", "Responsável", "Justificativa"]
        for item in items:
            rows.append([item.inventory.number, timezone.localtime(item.inventory.started_at).strftime("%d/%m/%Y"), item.product.name, decimal_text(item.system_quantity), decimal_text(item.counted_quantity), decimal_text(item.difference), "Sim" if item.adjusted else "Não", item.inventory.user.get_full_name() or item.inventory.user.username, item.justification or "-"])
        summary = {"divergences": len(rows)}

    return {
        "report_type": report_type,
        "title": title,
        "period": f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        "generated_by": user.get_full_name() or user.username,
        "filters": filters_used(params),
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "empty_message": "Nenhum registro foi encontrado com os filtros selecionados." if not rows else "",
    }


def build_report_data(report_type, params, user):
    if report_type == "daily_movements":
        return daily_data(params, user)
    return generic_report_data(report_type, params, user)
