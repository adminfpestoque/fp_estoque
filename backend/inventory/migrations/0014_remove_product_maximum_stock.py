from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("inventory", "0013_stockoutput_payment_due_date")]

    operations = [
        migrations.RemoveConstraint(
            model_name="product",
            name="inventory_product_nonnegative_values",
        ),
        migrations.RemoveField(
            model_name="product",
            name="maximum_stock",
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=Q(
                    cost_price__gte=0,
                    sale_price__gte=0,
                    stock__gte=0,
                    minimum_stock__gte=0,
                    package_quantity__gt=0,
                ),
                name="inventory_product_nonnegative_values",
            ),
        ),
    ]
