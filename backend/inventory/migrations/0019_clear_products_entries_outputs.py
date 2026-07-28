from django.db import migrations
from django.db.models import Q


OPERATIONAL_AUDIT_ENTITIES = [
    "Product",
    "ProductPackaging",
    "ProductSupplier",
    "Lot",
    "StockEntry",
    "StockEntryItem",
    "StockOutput",
    "StockOutputItem",
    "Movement",
    "StockAdjustment",
    "InventoryCount",
    "InventoryItem",
]


def clear_products_entries_outputs(apps, schema_editor):
    """Remove only product and stock-operation data, preserving master data."""
    database = schema_editor.connection.alias

    Product = apps.get_model("inventory", "Product")
    ProductPackaging = apps.get_model("inventory", "ProductPackaging")
    ProductSupplier = apps.get_model("inventory", "ProductSupplier")
    Lot = apps.get_model("inventory", "Lot")
    StockEntry = apps.get_model("inventory", "StockEntry")
    StockOutput = apps.get_model("inventory", "StockOutput")
    Movement = apps.get_model("inventory", "Movement")
    StockAdjustment = apps.get_model("inventory", "StockAdjustment")
    InventoryCount = apps.get_model("inventory", "InventoryCount")
    Alert = apps.get_model("inventory", "Alert")
    Notification = apps.get_model("inventory", "Notification")
    AuditLog = apps.get_model("inventory", "AuditLog")

    related_alerts = Alert.objects.using(database).filter(
        Q(product_id__isnull=False)
        | Q(lot_id__isnull=False)
        | Q(inventory_id__isnull=False)
        | Q(output_id__isnull=False)
    )

    # Remove somente notificações ligadas aos dados operacionais apagados.
    Notification.objects.using(database).filter(alert__in=related_alerts).delete()
    related_alerts.delete()

    # Remove os registros de auditoria referentes aos cadastros e operações limpos.
    AuditLog.objects.using(database).filter(
        entity__in=OPERATIONAL_AUDIT_ENTITIES
    ).delete()

    # Inventários e ajustes mantêm relações PROTECT com produtos e movimentações.
    InventoryCount.objects.using(database).all().delete()
    StockAdjustment.objects.using(database).all().delete()

    # Quebra apenas os vínculos internos necessários para apagar todo o histórico
    # de movimentações, inclusive estornos relacionados entre si.
    Movement.objects.using(database).all().update(
        reversal_of_id=None,
        entry_id=None,
        output_id=None,
        lot_id=None,
        product_id=None,
    )
    Movement.objects.using(database).all().delete()

    # Itens são removidos por CASCADE junto com os documentos.
    StockOutput.objects.using(database).all().delete()
    StockEntry.objects.using(database).all().delete()

    # Limpa dados dependentes dos produtos antes do cadastro principal.
    Lot.objects.using(database).all().delete()
    ProductPackaging.objects.using(database).all().delete()
    ProductSupplier.objects.using(database).all().delete()
    Product.objects.using(database).all().delete()


def reverse_noop(apps, schema_editor):
    # Exclusão de dados não possui reversão automática segura.
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0018_harden_alerts_and_notifications")]

    operations = [
        migrations.RunPython(clear_products_entries_outputs, reverse_noop),
    ]
