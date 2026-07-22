from datetime import datetime, time
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone

from ..models import Movement


def parse_date(value, fallback=None):
    if not value:
        return fallback
    return datetime.strptime(value, "%Y-%m-%d").date()


def report_period(params):
    today = timezone.localdate()
    selected = parse_date(params.get("date"))
    start = parse_date(params.get("start_date"), selected or today)
    end = parse_date(params.get("end_date"), selected or start)
    if end < start:
        start, end = end, start
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    end_dt = timezone.make_aware(datetime.combine(end, time.max))
    return start, end, start_dt, end_dt


def movement_queryset(params):
    start, end, start_dt, end_dt = report_period(params)
    qs = Movement.objects.select_related(
        "product", "product__category", "product__supplier", "lot", "user"
    ).filter(created_at__range=(start_dt, end_dt))
    mapping = {
        "product": "product_id",
        "category": "product__category_id",
        "supplier": "product__supplier_id",
        "movement_type": "type",
        "user": "user_id",
        "lot": "lot_id",
    }
    for param, field in mapping.items():
        value = params.get(param)
        if value:
            qs = qs.filter(**{field: value})
    brand = params.get("brand")
    if brand:
        qs = qs.filter(product__brand__icontains=brand)
    stock_status = params.get("stock_status")
    if stock_status == "low":
        qs = qs.filter(product__stock__lte=F("product__minimum_stock"), product__stock__gt=0)
    elif stock_status == "out":
        qs = qs.filter(product__stock=0)
    elif stock_status == "normal":
        qs = qs.filter(product__stock__gt=F("product__minimum_stock"))
    search = params.get("search")
    if search:
        qs = qs.filter(
            Q(product__name__icontains=search)
            | Q(product__code__icontains=search)
            | Q(reason__icontains=search)
            | Q(document__icontains=search)
        )
    return qs.order_by("created_at"), (start, end, start_dt, end_dt)


def money(value):
    value = Decimal(value or 0)
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def decimal_text(value):
    return f"{Decimal(value or 0):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def filters_used(params):
    labels = {
        "date": "Data",
        "start_date": "Data inicial",
        "end_date": "Data final",
        "product": "Produto",
        "category": "Categoria",
        "supplier": "Fornecedor",
        "movement_type": "Tipo de movimentação",
        "user": "Usuário",
        "lot": "Lote",
        "stock_status": "Situação do estoque",
        "brand": "Marca",
        "search": "Pesquisa",
    }
    return [f"{labels[k]}: {v}" for k, v in params.items() if k in labels and v]


def reconstruct_stock_at(product, end_dt):
    later = product.movements.filter(created_at__gt=end_dt)
    increase = later.filter(type__in=Movement.INCREASE_TYPES).aggregate(v=Sum("quantity"))["v"] or 0
    decrease = later.filter(type__in=Movement.DECREASE_TYPES).aggregate(v=Sum("quantity"))["v"] or 0
    return Decimal(product.stock) - Decimal(increase) + Decimal(decrease)
