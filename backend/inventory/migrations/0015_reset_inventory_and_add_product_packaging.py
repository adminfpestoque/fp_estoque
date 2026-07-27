from django.db import migrations, models
import django.db.models.deletion


DEFAULT_PACKAGING = [
    "LATA",
    "GARRAFA",
    "GARRAFA PET",
    "GARRAFA LONG NECK",
    "GARRAFA RETORNÁVEL",
    "GARRAFA PIRIGUETE",
    "PACOTE",
]


def reset_inventory_database(apps, schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    preserved_models = {"UserProfile", "SystemSetting"}
    inventory_models = [
        model
        for model in apps.get_app_config("inventory").get_models()
        if model.__name__ not in preserved_models
    ]
    tables = sorted({model._meta.db_table for model in inventory_models})

    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            quoted_tables = ", ".join(quote(table) for table in tables)
            if quoted_tables:
                cursor.execute(
                    f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"
                )
        else:
            with connection.constraint_checks_disabled():
                for table in reversed(tables):
                    cursor.execute(f"DELETE FROM {quote(table)}")

    PackagingType = apps.get_model("inventory", "PackagingType")
    PackagingType.objects.bulk_create(
        [PackagingType(name=name, active=True) for name in DEFAULT_PACKAGING]
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0014_remove_product_maximum_stock")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="packaging",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="inventory.packagingtype",
            ),
        ),
        migrations.RunPython(reset_inventory_database, noop_reverse),
        migrations.AlterField(
            model_name="product",
            name="packaging",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="inventory.packagingtype",
            ),
        ),
    ]
