from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
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


def refresh_alerts(notify=True):
    today = timezone.localdate()
    days = SystemSetting.get_int("expiration_alert_days", 30)
    limit = today + timedelta(days=days)
    Alert.objects.filter(active=True).update(active=False, resolved_at=timezone.now())
    alerts = []

    for product in Product.objects.filter(active=True):
        if product.stock <= 0:
            alerts.append(
                Alert.objects.create(
                    type=Alert.OUT_OF_STOCK,
                    level=Alert.CRITICAL,
                    product=product,
                    message=f"{product.name} está sem estoque.",
                )
            )
        elif product.stock <= product.minimum_stock:
            alerts.append(
                Alert.objects.create(
                    type=Alert.LOW_STOCK,
                    level=Alert.WARNING,
                    product=product,
                    message=f"{product.name} atingiu o estoque mínimo ({product.stock}).",
                )
            )

    for lot in Lot.objects.select_related("product").filter(active=True, quantity__gt=0):
        if lot.expiration_date and lot.expiration_date < today:
            alerts.append(
                Alert.objects.create(
                    type=Alert.EXPIRED,
                    level=Alert.CRITICAL,
                    product=lot.product,
                    lot=lot,
                    message=f"O lote {lot.number} de {lot.product.name} está vencido.",
                )
            )
        elif lot.expiration_date and lot.expiration_date <= limit:
            alerts.append(
                Alert.objects.create(
                    type=Alert.EXPIRING,
                    level=Alert.WARNING,
                    product=lot.product,
                    lot=lot,
                    message=f"O lote {lot.number} de {lot.product.name} vence em {lot.expiration_date:%d/%m/%Y}.",
                )
            )

    divergence_items = InventoryItem.objects.select_related("inventory", "product").filter(
        inventory__status__in=["OPEN", "WAITING"]
    ).exclude(system_quantity=F("counted_quantity"))
    for item in divergence_items:
        alerts.append(
            Alert.objects.create(
                type=Alert.INVENTORY_DIVERGENCE,
                level=Alert.WARNING,
                product=item.product,
                inventory=item.inventory,
                message=f"Divergência de {item.difference} em {item.product.name} no inventário {item.inventory.number}.",
            )
        )

    if notify and alerts:
        users = get_user_model().objects.filter(is_active=True)
        notifications = []
        for user in users:
            for item in alerts:
                notifications.append(
                    Notification(
                        user=user,
                        alert=item,
                        title=item.get_type_display(),
                        message=item.message,
                        level=item.level,
                    )
                )
        Notification.objects.bulk_create(notifications)
    return alerts
