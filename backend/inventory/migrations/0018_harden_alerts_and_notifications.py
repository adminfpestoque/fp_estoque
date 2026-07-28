from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
from django.utils import timezone


def merge_notification(keeper, duplicate):
    changed = False
    if not duplicate.read and keeper.read:
        keeper.read = False
        keeper.read_at = None
        changed = True
    if duplicate.created_at > keeper.created_at:
        keeper.title = duplicate.title
        keeper.message = duplicate.message
        keeper.level = duplicate.level
        changed = True
    if changed:
        keeper.save(
            update_fields=[
                "title",
                "message",
                "level",
                "read",
                "read_at",
                "updated_at",
            ]
        )


def deduplicate_alerts_and_notifications(apps, schema_editor):
    Alert = apps.get_model("inventory", "Alert")
    Notification = apps.get_model("inventory", "Notification")
    now = timezone.now()

    active_by_key = {}
    alerts = Alert.objects.filter(active=True).order_by("-created_at", "-pk")
    for alert in alerts:
        key = (
            alert.type,
            alert.product_id,
            alert.lot_id,
            alert.inventory_id,
            alert.output_id,
        )
        keeper = active_by_key.get(key)
        if keeper is None:
            active_by_key[key] = alert
            continue

        for duplicate_notification in Notification.objects.filter(alert_id=alert.pk):
            existing = Notification.objects.filter(
                user_id=duplicate_notification.user_id,
                alert_id=keeper.pk,
            ).first()
            if existing:
                merge_notification(existing, duplicate_notification)
                duplicate_notification.delete()
            else:
                duplicate_notification.alert_id = keeper.pk
                duplicate_notification.save(update_fields=["alert", "updated_at"])

        alert.active = False
        alert.resolved_at = now
        alert.save(update_fields=["active", "resolved_at", "updated_at"])

    notification_by_key = {}
    notifications = (
        Notification.objects.filter(alert__isnull=False)
        .order_by("-created_at", "-pk")
    )
    for notification in notifications:
        key = (notification.user_id, notification.alert_id)
        keeper = notification_by_key.get(key)
        if keeper is None:
            notification_by_key[key] = notification
            continue
        merge_notification(keeper, notification)
        notification.delete()

    Notification.objects.filter(read=True, read_at__isnull=True).update(
        read_at=now,
        updated_at=now,
    )
    Notification.objects.filter(read=False).exclude(read_at__isnull=True).update(
        read_at=None,
        updated_at=now,
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0017_restore_packaging_group_types")]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="output",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="alerts",
                to="inventory.stockoutput",
            ),
        ),
        migrations.RunPython(
            deduplicate_alerts_and_notifications,
            reverse_noop,
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["active", "output"],
                name="inv_alert_active_output_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["user", "read", "-created_at"],
                name="inv_notif_user_read_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("type", "product"),
                condition=Q(
                    active=True,
                    product__isnull=False,
                    lot__isnull=True,
                    inventory__isnull=True,
                    output__isnull=True,
                ),
                name="inv_alert_active_product_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("type", "lot"),
                condition=Q(active=True, lot__isnull=False),
                name="inv_alert_active_lot_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("type", "inventory", "product"),
                condition=Q(active=True, inventory__isnull=False),
                name="inv_alert_active_inv_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("type", "output"),
                condition=Q(active=True, output__isnull=False),
                name="inv_alert_active_output_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=("user", "alert"),
                condition=Q(alert__isnull=False),
                name="inv_notif_user_alert_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.CheckConstraint(
                condition=(
                    Q(read=False, read_at__isnull=True)
                    | Q(read=True, read_at__isnull=False)
                ),
                name="inv_notif_read_state_valid",
            ),
        ),
    ]
