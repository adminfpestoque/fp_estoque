from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def migrate_existing_outputs(apps, schema_editor):
    StockOutput = apps.get_model("inventory", "StockOutput")
    StockOutputItem = apps.get_model("inventory", "StockOutputItem")
    Movement = apps.get_model("inventory", "Movement")

    for item in StockOutputItem.objects.select_related("product", "output").iterator():
        quantity = Decimal(item.quantity or 0)
        sale_quantity = max(int(quantity), 1)
        movement = (
            Movement.objects.filter(
                output_id=item.output_id,
                product_id=item.product_id,
                reversal_of__isnull=True,
            )
            .order_by("created_at", "pk")
            .first()
        )
        price = Decimal("0.00")
        if movement and movement.unit_sale_price is not None:
            price = movement.unit_sale_price
        elif item.product_id and item.product.sale_price is not None:
            price = item.product.sale_price
        item.sale_quantity = sale_quantity
        item.conversion_factor = 1
        item.sale_unit_name = "Unidade"
        item.unit_sale_price = price
        item.save(
            update_fields=[
                "sale_quantity",
                "conversion_factor",
                "sale_unit_name",
                "unit_sale_price",
            ]
        )

    for output in StockOutput.objects.all().iterator():
        total = sum(
            (
                Decimal(item.quantity or 0) * Decimal(item.unit_sale_price or 0)
                for item in StockOutputItem.objects.filter(output_id=output.pk)
            ),
            Decimal("0.00"),
        )
        output.total_value = total.quantize(Decimal("0.01"))
        if output.reason == "COMMERCIAL" and output.status == "CONFIRMED":
            output.payment_method = "OTHER"
            output.amount_received = output.total_value
        else:
            output.payment_method = "NONE"
            output.amount_received = Decimal("0.00")
        output.save(
            update_fields=["total_value", "payment_method", "amount_received"]
        )


def reverse_existing_outputs(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0008_user_accessibility_preferences")]

    operations = [
        migrations.CreateModel(
            name="ProductPackaging",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("BOX", "Caixa"),
                            ("BUNDLE", "Fardo"),
                            ("CRATE", "Grade/engradado"),
                            ("PACK", "Pacote"),
                            ("TRAY", "Bandeja"),
                            ("BAG", "Saco"),
                            ("OTHER", "Outra"),
                        ],
                        default="BOX",
                        max_length=16,
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("units_per_package", models.PositiveIntegerField()),
                ("active", models.BooleanField(default=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="packaging_options",
                        to="inventory.product",
                    ),
                ),
            ],
            options={"ordering": ["units_per_package", "name"]},
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="customer_name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("NONE", "Não se aplica"),
                    ("CASH", "Dinheiro"),
                    ("PIX", "Pix"),
                    ("DEBIT", "Cartão de débito"),
                    ("CREDIT", "Cartão de crédito"),
                    ("TRANSFER", "Transferência"),
                    ("ON_ACCOUNT", "A prazo/fiado"),
                    ("OTHER", "Outro"),
                ],
                default="NONE",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="total_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="amount_received",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="stockoutput",
            name="payment_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="packaging",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="output_items",
                to="inventory.productpackaging",
            ),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="sale_unit_name",
            field=models.CharField(default="Unidade", max_length=50),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="sale_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="conversion_factor",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="unit_sale_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(migrate_existing_outputs, reverse_existing_outputs),
        migrations.AddConstraint(
            model_name="productpackaging",
            constraint=models.UniqueConstraint(
                fields=("product", "name"),
                name="inv_product_packaging_name_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="productpackaging",
            constraint=models.CheckConstraint(
                condition=Q(units_per_package__gt=1),
                name="inv_product_packaging_units_gt_one",
            ),
        ),
        migrations.AddIndex(
            model_name="stockoutput",
            index=models.Index(
                fields=["payment_method", "output_date"],
                name="inv_output_payment_date_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockoutput",
            constraint=models.CheckConstraint(
                condition=Q(total_value__gte=0, amount_received__gte=0),
                name="inv_output_payment_values_nonnegative",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="stockoutputitem",
            name="inv_output_item_qty_valid",
        ),
        migrations.AddConstraint(
            model_name="stockoutputitem",
            constraint=models.CheckConstraint(
                condition=Q(
                    quantity__gt=0,
                    sale_quantity__gt=0,
                    conversion_factor__gt=0,
                    unit_sale_price__gte=0,
                ),
                name="inv_output_item_values_valid",
            ),
        ),
    ]
