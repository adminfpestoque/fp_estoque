import re

from django.db import migrations, models


VOLUME_PATTERN = re.compile(r"^(?P<package>.*?)(?:\s+)?(?P<volume>\d+)\s*(?P<unit>ml|l)\s*$", re.IGNORECASE)


def split_existing_package_volume(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    for product in Product.objects.exclude(package_type="").iterator():
        match = VOLUME_PATTERN.match((product.package_type or "").strip())
        if not match:
            continue
        product.package_type = match.group("package").strip(" -–—")
        product.volume = int(match.group("volume"))
        product.volume_unit = match.group("unit").upper()
        product.save(update_fields=["package_type", "volume", "volume_unit"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0004_complete_inventory_workflow")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="volume",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="volume_unit",
            field=models.CharField(
                choices=[("ML", "Mililitros (ML)"), ("L", "Litros (L)")],
                default="ML",
                max_length=2,
            ),
        ),
        migrations.RunPython(split_existing_package_volume, migrations.RunPython.noop),
    ]
