from django.conf import settings
from django.db import models
from django.db.models import Q

from .base import TimeStamped
from .catalog import Lot, Product
from .counts import InventoryCount


class Alert(TimeStamped):
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    INVENTORY_DIVERGENCE = "INVENTORY_DIVERGENCE"
    CREDIT_DUE = "CREDIT_DUE"
    CREDIT_OVERDUE = "CREDIT_OVERDUE"
    TYPES = [
        (LOW_STOCK, "Estoque baixo"),
        (OUT_OF_STOCK, "Sem estoque"),
        (EXPIRING, "Próximo do vencimento"),
        (EXPIRED, "Vencido"),
        (INVENTORY_DIVERGENCE, "Divergência de inventário"),
        (CREDIT_DUE, "Pagamento a vencer"),
        (CREDIT_OVERDUE, "Pagamento vencido"),
    ]

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    LEVELS = [(INFO, "Informativo"), (WARNING, "Atenção"), (CRITICAL, "Crítico")]

    type = models.CharField(max_length=30, choices=TYPES)
    level = models.CharField(max_length=10, choices=LEVELS)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
    )
    lot = models.ForeignKey(
        Lot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
    )
    inventory = models.ForeignKey(
        InventoryCount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
    )
    output = models.ForeignKey(
        "inventory.StockOutput",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    message = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-active", "-created_at"]
        indexes = [
            models.Index(fields=["active", "type"], name="inv_alert_active_type_idx"),
            models.Index(fields=["active", "output"], name="inv_alert_active_output_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["type", "product"],
                condition=Q(
                    active=True,
                    product__isnull=False,
                    lot__isnull=True,
                    inventory__isnull=True,
                    output__isnull=True,
                ),
                name="inv_alert_active_product_uniq",
            ),
            models.UniqueConstraint(
                fields=["type", "lot"],
                condition=Q(active=True, lot__isnull=False),
                name="inv_alert_active_lot_uniq",
            ),
            models.UniqueConstraint(
                fields=["type", "inventory", "product"],
                condition=Q(active=True, inventory__isnull=False),
                name="inv_alert_active_inv_uniq",
            ),
            models.UniqueConstraint(
                fields=["type", "output"],
                condition=Q(active=True, output__isnull=False),
                name="inv_alert_active_output_uniq",
            ),
        ]


class Notification(TimeStamped):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_notifications",
    )
    alert = models.ForeignKey(
        Alert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    title = models.CharField(max_length=160)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=Alert.LEVELS, default=Alert.INFO)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "read", "-created_at"],
                name="inv_notif_user_read_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "alert"],
                condition=Q(alert__isnull=False),
                name="inv_notif_user_alert_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(read=False, read_at__isnull=True)
                    | Q(read=True, read_at__isnull=False)
                ),
                name="inv_notif_read_state_valid",
            ),
        ]


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["entity", "created_at"],
                name="inv_audit_entity_date_idx",
            )
        ]


class SystemSetting(TimeStamped):
    key = models.CharField(max_length=80, unique=True)
    value = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["key"]

    @classmethod
    def get_int(cls, key: str, default: int) -> int:
        try:
            return int(cls.objects.get(key=key).value)
        except (cls.DoesNotExist, TypeError, ValueError):
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = True) -> bool:
        try:
            value = str(cls.objects.get(key=key).value).strip().lower()
        except cls.DoesNotExist:
            return default
        if value in {"1", "true", "sim", "yes", "on"}:
            return True
        if value in {"0", "false", "não", "nao", "no", "off"}:
            return False
        return default
