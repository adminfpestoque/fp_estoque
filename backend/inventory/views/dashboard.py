from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Q, Sum, When
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import Alert, Category, Lot, Movement, Product, StockOutput, SystemSetting
from ..permissions import IsInventoryUser
from ..serializers import AlertSerializer, MovementSerializer

ZERO = Decimal("0")
MONEY_FIELD = DecimalField(max_digits=30, decimal_places=2)
QUANTITY_FIELD = DecimalField(max_digits=24, decimal_places=3)
PRICE_FIELD = DecimalField(max_digits=12, decimal_places=2)


def _decimal(value):
    return value if value is not None else ZERO


def _margin(profit, revenue):
    if not revenue:
        return ZERO
    return ((profit / revenue) * Decimal("100")).quantize(Decimal("0.01"))


def _parse_optional_id(value, label):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} inválido.") from exc
    if parsed <= 0:
        raise ValueError(f"{label} inválido.")
    return parsed


@api_view(["GET"])
@permission_classes([IsInventoryUser])
def dashboard(request):
    period = request.GET.get("period", "today")
    today = timezone.localdate()

    try:
        if period == "7d":
            start = today - timedelta(days=6)
        elif period == "month":
            start = today.replace(day=1)
        elif period == "custom":
            start = datetime.strptime(
                request.GET.get("start_date", str(today)), "%Y-%m-%d"
            ).date()
        else:
            start = today

        end = (
            datetime.strptime(
                request.GET.get("end_date", str(today)), "%Y-%m-%d"
            ).date()
            if period == "custom"
            else today
        )
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")

        product_id = _parse_optional_id(request.GET.get("product"), "Produto")
        category_id = _parse_optional_id(request.GET.get("category"), "Categoria")
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    all_products = Product.objects.filter(active=True).select_related("category")
    selected_product = all_products.filter(pk=product_id).first() if product_id else None
    selected_category = (
        Category.objects.filter(active=True, pk=category_id).first()
        if category_id
        else None
    )

    products = all_products
    if category_id:
        products = products.filter(category_id=category_id)
    if product_id:
        products = products.filter(pk=product_id)

    product_list = list(products.order_by("name"))
    product_ids = [product.pk for product in product_list]

    movements = Movement.objects.filter(
        product_id__in=product_ids,
        created_at__date__range=(start, end),
    )
    entries = movements.filter(type__in=Movement.INCREASE_TYPES)
    outputs = movements.filter(type__in=Movement.DECREASE_TYPES)

    effective_sale_price = Case(
        When(unit_sale_price__gt=0, then=F("unit_sale_price")),
        default=F("product__sale_price"),
        output_field=PRICE_FIELD,
    )
    revenue_expression = ExpressionWrapper(
        F("quantity") * effective_sale_price,
        output_field=MONEY_FIELD,
    )
    cost_expression = ExpressionWrapper(
        F("quantity") * F("unit_cost"),
        output_field=MONEY_FIELD,
    )

    commercial_sales = Movement.objects.filter(
        product_id__in=product_ids,
        type=Movement.OUTPUT,
        reversed=False,
        output__status=StockOutput.CONFIRMED,
        output__reason="COMMERCIAL",
        output__output_date__date__range=(start, end),
    )

    sales_totals = commercial_sales.aggregate(
        sold_quantity=Sum("quantity", output_field=QUANTITY_FIELD),
        revenue=Sum(revenue_expression, output_field=MONEY_FIELD),
        cost=Sum(cost_expression, output_field=MONEY_FIELD),
    )
    sold_quantity = _decimal(sales_totals["sold_quantity"])
    sales_revenue = _decimal(sales_totals["revenue"])
    cost_of_sales = _decimal(sales_totals["cost"])
    gross_profit = sales_revenue - cost_of_sales

    stock_cost_expression = ExpressionWrapper(
        F("stock") * F("cost_price"), output_field=MONEY_FIELD
    )
    stock_sale_expression = ExpressionWrapper(
        F("stock") * F("sale_price"), output_field=MONEY_FIELD
    )
    stock_totals = products.aggregate(
        quantity=Sum("stock", output_field=QUANTITY_FIELD),
        cost_value=Sum(stock_cost_expression, output_field=MONEY_FIELD),
        sale_value=Sum(stock_sale_expression, output_field=MONEY_FIELD),
    )
    current_stock = _decimal(stock_totals["quantity"])
    current_stock_cost = _decimal(stock_totals["cost_value"])
    current_stock_sale = _decimal(stock_totals["sale_value"])

    sales_by_product = {
        row["product_id"]: row
        for row in commercial_sales.values("product_id").annotate(
            quantity_sold=Sum("quantity", output_field=QUANTITY_FIELD),
            revenue=Sum(revenue_expression, output_field=MONEY_FIELD),
            cost=Sum(cost_expression, output_field=MONEY_FIELD),
        )
    }

    product_performance = []
    for product in product_list:
        sold = sales_by_product.get(product.pk, {})
        quantity_sold = _decimal(sold.get("quantity_sold"))
        revenue = _decimal(sold.get("revenue"))
        cost = _decimal(sold.get("cost"))
        profit = revenue - cost
        stock_cost_value = product.stock * product.cost_price
        stock_sale_value = product.stock * product.sale_price

        product_performance.append(
            {
                "id": product.pk,
                "code": product.code,
                "name": product.name,
                "category_id": product.category_id,
                "category": product.category.name,
                "unit_cost": product.cost_price,
                "unit_sale_price": product.sale_price,
                "quantity_sold": quantity_sold,
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "margin_percent": _margin(profit, revenue),
                "current_stock": product.stock,
                "stock_cost_value": stock_cost_value,
                "stock_sale_value": stock_sale_value,
                "stock_profit_potential": stock_sale_value - stock_cost_value,
            }
        )

    product_performance.sort(
        key=lambda row: (
            row["revenue"],
            row["quantity_sold"],
            row["current_stock"],
        ),
        reverse=True,
    )

    category_performance_map = {}
    for row in product_performance:
        summary = category_performance_map.setdefault(
            row["category_id"],
            {
                "category_id": row["category_id"],
                "category": row["category"],
                "quantity_sold": ZERO,
                "revenue": ZERO,
                "cost": ZERO,
                "profit": ZERO,
                "current_stock": ZERO,
                "stock_cost_value": ZERO,
                "stock_sale_value": ZERO,
            },
        )
        for key in (
            "quantity_sold",
            "revenue",
            "cost",
            "profit",
            "current_stock",
            "stock_cost_value",
            "stock_sale_value",
        ):
            summary[key] += row[key]

    category_performance = sorted(
        category_performance_map.values(),
        key=lambda row: (row["revenue"], row["current_stock"]),
        reverse=True,
    )
    for row in category_performance:
        row["margin_percent"] = _margin(row["profit"], row["revenue"])

    movement_chart_qs = (
        movements.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            entries=Sum(
                "quantity", filter=Q(type__in=Movement.INCREASE_TYPES)
            ),
            outputs=Sum(
                "quantity", filter=Q(type__in=Movement.DECREASE_TYPES)
            ),
            total=Count("id"),
        )
        .order_by("day")
    )

    sales_chart_qs = (
        commercial_sales.annotate(day=TruncDate("output__output_date"))
        .values("day")
        .annotate(
            sold_quantity=Sum("quantity", output_field=QUANTITY_FIELD),
            revenue=Sum(revenue_expression, output_field=MONEY_FIELD),
            cost=Sum(cost_expression, output_field=MONEY_FIELD),
        )
        .order_by("day")
    )

    category_stock = [
        {
            "category__name": row["category"],
            "quantity": row["current_stock"],
            "value": row["stock_cost_value"],
        }
        for row in category_performance
    ]

    if selected_product:
        scope_label = f"{selected_product.code} — {selected_product.name}"
    elif selected_category:
        scope_label = f"Categoria: {selected_category.name}"
    else:
        scope_label = "Todos os produtos"

    expiry_days = SystemSetting.get_int("expiration_alert_days", 30)
    recent = movements.select_related(
        "product", "product__category", "user", "lot"
    )[:10]
    alerts = Alert.objects.filter(
        active=True, product_id__in=product_ids
    ).select_related("product", "lot")[:10]

    return Response(
        {
            "period": {"start": start, "end": end},
            "scope": {
                "label": scope_label,
                "product_id": product_id,
                "category_id": category_id,
            },
            "filter_options": {
                "categories": list(
                    Category.objects.filter(active=True)
                    .order_by("name")
                    .values("id", "name")
                ),
                "products": list(
                    all_products.order_by("name").values(
                        "id", "code", "name", "category_id"
                    )
                ),
            },
            "products": len(product_list),
            "stock_items": current_stock,
            "low_stock": products.filter(
                stock__lte=F("minimum_stock"), stock__gt=0
            ).count(),
            "out_of_stock": products.filter(stock=0).count(),
            "expiring": Lot.objects.filter(
                product_id__in=product_ids,
                quantity__gt=0,
                expiration_date__gte=today,
                expiration_date__lte=today + timedelta(days=expiry_days),
            ).count(),
            "expired": Lot.objects.filter(
                product_id__in=product_ids,
                quantity__gt=0,
                expiration_date__lt=today,
            ).count(),
            "inventory_value": current_stock_cost,
            "stock_sale_value": current_stock_sale,
            "stock_profit_potential": current_stock_sale - current_stock_cost,
            "entries_period": entries.aggregate(v=Sum("quantity"))["v"] or ZERO,
            "outputs_period": outputs.aggregate(v=Sum("quantity"))["v"] or ZERO,
            "sales": {
                "quantity_sold": sold_quantity,
                "revenue": sales_revenue,
                "cost": cost_of_sales,
                "gross_profit": gross_profit,
                "margin_percent": _margin(gross_profit, sales_revenue),
                "sales_documents": commercial_sales.exclude(output_id=None)
                .values("output_id")
                .distinct()
                .count(),
                "products_sold": commercial_sales.values("product_id")
                .distinct()
                .count(),
                "current_stock": current_stock,
                "current_stock_cost": current_stock_cost,
                "current_stock_sale": current_stock_sale,
                "stock_profit_potential": current_stock_sale - current_stock_cost,
            },
            "product_performance": product_performance[:30],
            "product_performance_total": len(product_performance),
            "category_performance": category_performance,
            "recent": MovementSerializer(recent, many=True).data,
            "alerts": AlertSerializer(alerts, many=True).data,
            "charts": {
                "movements": [
                    {
                        "date": row["day"],
                        "entries": row["entries"] or ZERO,
                        "outputs": row["outputs"] or ZERO,
                        "total": row["total"],
                    }
                    for row in movement_chart_qs
                ],
                "sales": [
                    {
                        "date": row["day"],
                        "quantity": row["sold_quantity"] or ZERO,
                        "revenue": row["revenue"] or ZERO,
                        "cost": row["cost"] or ZERO,
                        "profit": (row["revenue"] or ZERO)
                        - (row["cost"] or ZERO),
                    }
                    for row in sales_chart_qs
                ],
                "product_sales": [
                    {
                        "name": row["name"],
                        "code": row["code"],
                        "quantity": row["quantity_sold"],
                        "revenue": row["revenue"],
                        "profit": row["profit"],
                        "stock": row["current_stock"],
                    }
                    for row in product_performance[:10]
                ],
                "category_stock": category_stock,
            },
        }
    )
