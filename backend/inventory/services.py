from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import Alert, AuditLog, InventoryItem, Lot, Notification, Product, SystemSetting


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


def _alert_key(*, type, product=None, lot=None, inventory=None, **_):
    return (
        type,
        getattr(product, "pk", None),
        getattr(lot, "pk", None),
        getattr(inventory, "pk", None),
    )


def _notification_users():
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(inventory_profile__active=True) | Q(inventory_profile__isnull=True))
        .distinct()
    )


def _notify_alert(alert, users):
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
        changed = (
            notification.title != title
            or notification.message != alert.message
            or notification.level != alert.level
            or notification.read
            or notification.read_at is not None
        )
        if changed:
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


def _build_alert_candidates():
    today = timezone.localdate()
    days = max(0, SystemSetting.get_int("expiration_alert_days", 30))
    limit = today + timedelta(days=days)
    candidates = []

    for product in Product.objects.filter(active=True):
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

    lots = Lot.objects.select_related("product").filter(active=True, quantity__gt=0)
    for lot in lots:
        if lot.expiration_date and lot.expiration_date < today:
            candidates.append(
                {
                    "type": Alert.EXPIRED,
                    "level": Alert.CRITICAL,
                    "product": lot.product,
                    "lot": lot,
                    "message": f"O lote {lot.number} de {lot.product.name} está vencido.",
                }
            )
        elif lot.expiration_date and lot.expiration_date <= limit:
            candidates.append(
                {
                    "type": Alert.EXPIRING,
                    "level": Alert.WARNING,
                    "product": lot.product,
                    "lot": lot,
                    "message": (
                        f"O lote {lot.number} de {lot.product.name} vence em "
                        f"{lot.expiration_date:%d/%m/%Y}."
                    ),
                }
            )

    divergence_items = (
        InventoryItem.objects.select_related("inventory", "product")
        .filter(
            counted=True,
            inventory__status__in=["OPEN", "WAITING"],
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

    return candidates


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
        .order_by("-created_at", "-pk")
    )
    for alert in existing:
        key = _alert_key(
            type=alert.type,
            product=alert.product,
            lot=alert.lot,
            inventory=alert.inventory,
        )
        if key in existing_by_key:
            duplicate_ids.append(alert.pk)
        else:
            existing_by_key[key] = alert

    if duplicate_ids:
        Alert.objects.filter(pk__in=duplicate_ids).update(active=False, resolved_at=now)

    users = list(_notification_users()) if notify else []
    synchronized = []
    candidate_keys = set()

    for candidate in candidates:
        key = _alert_key(**candidate)
        candidate_keys.add(key)
        alert = existing_by_key.get(key)
        should_notify = False

        if alert is None:
            alert = Alert.objects.create(**candidate)
            should_notify = True
        else:
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
        if notify and should_notify:
            _notify_alert(alert, users)

    stale_ids = [
        alert.pk
        for key, alert in existing_by_key.items()
        if key not in candidate_keys
    ]
    if stale_ids:
        Alert.objects.filter(pk__in=stale_ids).update(active=False, resolved_at=now)

    return synchronized
