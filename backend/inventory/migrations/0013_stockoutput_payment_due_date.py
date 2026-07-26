from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0012_remove_category_packaging_types")]

    operations = [
        migrations.AddField(
            model_name="stockoutput",
            name="payment_due_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
