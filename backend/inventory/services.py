from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import (
    Alert,
    AuditLog,
    InventoryItem,
    Lot,
    Notification,
    Product,
    StockOutput,
    SystemSetting,
)


def audit(user, action, instance=None, description="", metadata=None):
    entity = instance.__class__.__name__ if instance is not None else "System"
    object_id = str(getattr(instance, "pk", "") or "")
    return AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        object_id=object_id,
        description=description,
        metadata=metadata or {},
    )


def _alert_key(*, type, product=None, lot=None, inventory=None, output=None, **_):
    return (
        type,
        getattr(product, "pk", None),
        getattr(lot, "pk", None),
        getattr(inventory, "pk", None),
        getattr(output, "pk", None),
    )


def _active_alert_filter(key):
    alert_type, product_id, lot_id, inventory_id, output_id = key
    return {
        "type": alert_type,
        "product_id": product_id,
        "lot_id": lot_id,
        "inventory_id": inventory_id,
        "output_id": output_id,
        "active": True,
    }


def _notification_users():
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(inventory_profile__active=True) | Q(inventory_profile__isnull=True))
        .distinct()
    )


def _notify_alert(alert, users, *, force_unread=False):
    """Ensure every active user has one notification for the alert."""
    now = timezone.now()
    title = alert.get_type_display()

    for user in users:
        notification, created = Notification.objects.get_or_create(
            user=user,
            alert=alert,
            defaults={
                "title": title,
                "message": alert.message,
                "level": alert.level,
            },
        )
        if created:
            continue

        content_changed = (
            notification.title != title
            or notification.message != alert.message
            or notification.level != alert.level
        )
        if not content_changed and not force_unread:
            continue

        notification.title = title
        notification.message = alert.message
        notification.level = alert.level
        notification.read = False
        notification.read_at = None
        notification.updated_at = now
        notification.save(
            update_fields=[
                "title",
                "message",
                "level",
                "read",
                "read_at",
                "updated_at",
            ]
        )


def notify_users(title, message, *, level=Alert.INFO, users=None):
    """Create a general system notification for active inventory users."""
    recipients = list(users) if users is not None else list(_notification_users())
    return [
        Notification.objects.create(
            user=user,
            title=str(title),
            message=str(message),
            level=level,
        )
        for user in recipients
    ]


def _money_br(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    formatted = f"{amount:,.2f}"
    return f"R$ {formatted.replace(',', '_').replace('.', ',').replace('_', '.')}"


def _build_alert_candidates():
    today = timezone.localdate()
    expiration_days = max(0, SystemSetting.get_int("expiration_alert_days", 30))
    expiration_limit = today + timedelta(days=expiration_days)
    candidates = []

    if SystemSetting.get_bool("stock_alerts_enabled", True):
        products = Product.objects.filter(active=True, deleted_at__isnull=True)
        for product in products:
            if product.stock <= 0:
                candidates.append(
                    {
                        "type": Alert.OUT_OF_STOCK,
                        "level": Alert.CRITICAL,
                        "product": product,
                        "message": f"{product.name} está sem estoque.",
                    }
                )
            elif product.stock <= product.minimum_stock:
                candidates.append(
                    {
                        "type": Alert.LOW_STOCK,
                        "level": Alert.WARNING,
                        "product": product,
                        "message": (
                            f"{product.name} atingiu o estoque mínimo "
                            f"({int(product.stock)} unidade(s))."
                        ),
                    }
                )

    if SystemSetting.get_bool("expiration_alerts_enabled", True):
        lots = Lot.objects.select_related("product").filter(
            active=True,
            quantity__gt=0,
            product__active=True,
            product__deleted_at__isnull=True,
        )
        for lot in lots:
            if lot.expiration_date and lot.expiration_date < today:
                candidates.append(
                    {
                        "type": Alert.EXPIRED,
                        "level": Alert.CRITICAL,
                        "product": lot.product,
                        "lot": lot,
                        "message": f"O lote {lot.number} de {lot.product_name} está vencido.",
                    }
                )
            elif lot.expiration_date and lot.expiration_date <= expiration_limit:
                candidates.append(
                    {
                        "type": Alert.EXPIRING,
                        "level": Alert.WARNING,
                        "product": lot.product,
                        "lot": lot,
                        "message": (
                            f"O lote {lot.number} de {lot.product_name} vence em "
                            f"{lot.expiration_date:%d/%m/%Y}."
                        ),
                    }
                )

    if SystemSetting.get_bool("inventory_divergence_alerts_enabled", True):
        divergence_items = (
            InventoryItem.objects.select_related("inventory", "product")
            .filter(
                counted=True,
                inventory__status__in=["OPEN", "WAITING"],
                product__active=True,
                product__deleted_at__isnull=True,
            )
            .exclude(system_quantity=F("counted_quantity"))
        )
        for item in divergence_items:
            candidates.append(
                {
                    "type": Alert.INVENTORY_DIVERGENCE,
                    "level": Alert.WARNING,
                    "product": item.product,
                    "inventory": item.inventory,
                    "message": (
                        f"Divergência de {int(item.difference)} unidade(s) em "
                        f"{item.product.name} no inventário {item.inventory.number}."
                    ),
                }
            )

    if SystemSetting.get_bool("credit_due_alerts_enabled", True):
        credit_days = max(0, SystemSetting.get_int("credit_due_alert_days", 3))
        credit_limit = today + timedelta(days=credit_days)
        pending_outputs = StockOutput.objects.filter(
            status=StockOutput.DRAFT,
            reason="COMMERCIAL",
            payment_method=StockOutput.PAYMENT_ON_ACCOUNT,
            payment_due_date__isnull=False,
            deleted_at__isnull=True,
        ).select_related("user")

        for output in pending_outputs:
            customer = output.customer_name.strip() or "Cliente não informado"
            amount = _money_br(output.total_value)
            due_date = output.payment_due_date

            if due_date < today:
                candidates.append(
                    {
                        "type": Alert.CREDIT_OVERDUE,
                        "level": Alert.CRITICAL,
                        "output": output,
                        "message": (
                            f"O pagamento da saída {output.number}, de {customer}, "
                            f"no valor de {amount}, venceu em {due_date:%d/%m/%Y}."
                        ),
                    }
                )
            elif due_date <= credit_limit:
                candidates.append(
                    {
                        "type": Alert.CREDIT_DUE,
                        "level": Alert.WARNING,
                        "output": output,
                        "message": (
                            f"O pagamento da saída {output.number}, de {customer}, "
                            f"no valor de {amount}, vence em {due_date:%d/%m/%Y}."
                        ),
                    }
                )

    return candidates


def _create_or_get_active_alert(candidate, key):
    try:
        with transaction.atomic():
            return Alert.objects.create(**candidate), True
    except IntegrityError:
        alert = (
            Alert.objects.select_for_update()
            .filter(**_active_alert_filter(key))
            .first()
        )
        if alert is None:
            raise
        return alert, False


@transaction.atomic
def refresh_alerts(notify=True):
    """Synchronize active alerts without duplicating alerts or notifications."""
    now = timezone.now()
    candidates = _build_alert_candidates()
    existing_by_key = {}
    duplicate_ids = []

    existing = (
        Alert.objects.select_for_update()
        .filter(active=True)
        .select_related("product", "lot", "inventory", "output")
        .order_by("-created_at", "-pk")
    )
    for alert in existing:
        key = _alert_key(
            type=alert.type,
            product=alert.product,
            lot=alert.lot,
            inventory=alert.inventory,
            output=alert.output,
        )
        if key in existing_by_key:
            duplicate_ids.append(alert.pk)
        else:
            existing_by_key[key] = alert

    if duplicate_ids:
        Alert.objects.filter(pk__in=duplicate_ids).update(
            active=False,
            resolved_at=now,
            updated_at=now,
        )
        Notification.objects.filter(
            alert_id__in=duplicate_ids,
            read=False,
        ).update(
            read=True,
            read_at=now,
            updated_at=now,
        )

    users = list(_notification_users()) if notify else []
    synchronized = []
    candidate_keys = set()

    for candidate in candidates:
        key = _alert_key(**candidate)
        candidate_keys.add(key)
        alert = existing_by_key.get(key)
        should_notify = False

        if alert is None:
            alert, created = _create_or_get_active_alert(candidate, key)
            existing_by_key[key] = alert
            should_notify = created
        else:
            created = False

        changed_fields = []
        for field in ("level", "message"):
            value = candidate[field]
            if getattr(alert, field) != value:
                setattr(alert, field, value)
                changed_fields.append(field)

        if alert.resolved_at is not None:
            alert.resolved_at = None
            changed_fields.append("resolved_at")
        if not alert.active:
            alert.active = True
            changed_fields.append("active")

        if changed_fields:
            changed_fields.append("updated_at")
            alert.save(update_fields=changed_fields)
            should_notify = True

        synchronized.append(alert)
        if notify:
            _notify_alert(alert, users, force_unread=should_notify)

    stale_ids = [
        alert.pk
        for key, alert in existing_by_key.items()
        if key not in candidate_keys
    ]
    if stale_ids:
        Alert.objects.filter(pk__in=stale_ids).update(
            active=False,
            resolved_at=now,
            updated_at=now,
        )
        Notification.objects.filter(
            alert_id__in=stale_ids,
            read=False,
        ).update(
            read=True,
            read_at=now,
            updated_at=now,
        )

    return synchronized
