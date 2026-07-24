from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fill_product_snapshots(apps, schema_editor):
    StockEntryItem = apps.get_model("inventory", "StockEntryItem")
    StockOutputItem = apps.get_model("inventory", "StockOutputItem")
    Movement = apps.get_model("inventory", "Movement")
    Lot = apps.get_model("inventory", "Lot")

    for item in StockEntryItem.objects.select_related("product").iterator():
        if item.product_id:
            item.product_name_snapshot = item.product.name
            item.product_code_snapshot = item.product.code
            item.save(update_fields=["product_name_snapshot", "product_code_snapshot"])

    for item in StockOutputItem.objects.select_related("product").iterator():
        if item.product_id:
            item.product_name_snapshot = item.product.name
            item.product_code_snapshot = item.product.code
            item.save(update_fields=["product_name_snapshot", "product_code_snapshot"])

    for movement in Movement.objects.select_related("product", "product__category").iterator():
        if movement.product_id:
            movement.product_name_snapshot = movement.product.name
            movement.product_code_snapshot = movement.product.code
            movement.category_name_snapshot = movement.product.category.name
            movement.unit_snapshot = movement.product.unit
            movement.save(
                update_fields=[
                    "product_name_snapshot",
                    "product_code_snapshot",
                    "category_name_snapshot",
                    "unit_snapshot",
                ]
            )

    for lot in Lot.objects.select_related("product").iterator():
        if lot.product_id:
            lot.product_name_snapshot = lot.product.name
            lot.product_code_snapshot = lot.product.code
            lot.save(update_fields=["product_name_snapshot", "product_code_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_product_volume"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="stockentry",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockentry",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="deleted_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="stockentry",
            name="deletion_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="deleted_outputs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="deletion_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="product_name_snapshot",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="product_code_snapshot",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name="stockentryitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="entry_items",
                to="inventory.product",
            ),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="product_name_snapshot",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="product_code_snapshot",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name="stockoutputitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="output_items",
                to="inventory.product",
            ),
        ),
        migrations.AddField(
            model_name="movement",
            name="product_name_snapshot",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="movement",
            name="product_code_snapshot",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="movement",
            name="category_name_snapshot",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="movement",
            name="unit_snapshot",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="movement",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="movements",
                to="inventory.product",
            ),
        ),
        migrations.AddField(
            model_name="lot",
            name="product_name_snapshot",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="lot",
            name="product_code_snapshot",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name="lot",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lots",
                to="inventory.product",
            ),
        ),
        migrations.RunPython(fill_product_snapshots, migrations.RunPython.noop),
    ]
