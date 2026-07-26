from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("inventory", "0011_alter_productpackaging_options_and_more")]

    operations = [
        migrations.RemoveField(
            model_name="category",
            name="packaging_types",
        ),
    ]
