from django.db import migrations, models


def add_unit_sale_price(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            "ALTER TABLE inventory_movement "
            "ADD COLUMN unit_sale_price decimal NOT NULL DEFAULT 0;"
        )
        return

    schema_editor.execute(
        "ALTER TABLE inventory_movement "
        "ADD COLUMN IF NOT EXISTS unit_sale_price numeric(12, 2) NOT NULL DEFAULT 0;"
    )


def remove_unit_sale_price(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            "ALTER TABLE inventory_movement DROP COLUMN unit_sale_price;"
        )
        return

    schema_editor.execute(
        "ALTER TABLE inventory_movement "
        "DROP COLUMN IF EXISTS unit_sale_price;"
    )


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_full_system_upgrade_marker")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_unit_sale_price, remove_unit_sale_price)
            ],
            state_operations=[
                migrations.AddField(
                    model_name="movement",
                    name="unit_sale_price",
                    field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
                )
            ],
        )
    ]
