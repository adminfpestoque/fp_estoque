from decimal import Decimal

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models
from django.db.models import Q


TYPE_LABELS = {
    "BOX": "Caixa",
    "BUNDLE": "Fardo",
    "CRATE": "Grade/engradado",
    "PACK": "Pacote",
    "TRAY": "Bandeja",
    "BAG": "Saco",
    "OTHER": "Outra",
}


def migrate_packaging_and_documents(apps, schema_editor):
    PackagingType = apps.get_model("inventory", "PackagingType")
    ProductPackaging = apps.get_model("inventory", "ProductPackaging")
    StockEntryItem = apps.get_model("inventory", "StockEntryItem")
    StockOutputItem = apps.get_model("inventory", "StockOutputItem")

    first_by_product = set()
    primary_by_product_type = {}
    category_packaging_links = set()
    for option in ProductPackaging.objects.select_related("product", "product__category").order_by(
        "product_id", "pk"
    ):
        name = " ".join(str(option.name or TYPE_LABELS.get(option.type) or "Embalagem").strip().split())
        packaging_type = PackagingType.objects.filter(name__iexact=name).first()
        if not packaging_type:
            packaging_type = PackagingType.objects.create(name=name)
        key = (option.product_id, packaging_type.pk)
        primary_id = primary_by_product_type.get(key)
        if primary_id:
            StockEntryItem.objects.filter(packaging_id=option.pk).update(packaging_id=primary_id)
            StockOutputItem.objects.filter(packaging_id=option.pk).update(packaging_id=primary_id)
            option.delete()
            continue
        primary_by_product_type[key] = option.pk
        option.packaging_type_id = packaging_type.pk
        factor = max(int(option.units_per_package or 1), 1)
        option.cost_price = (Decimal(option.product.cost_price or 0) * factor).quantize(Decimal("0.01"))
        # O preço já cadastrado no produto passa a ser o valor inicial da forma de venda.
        # Isso evita multiplicar automaticamente o preço por todas as unidades da embalagem.
        option.sale_price = Decimal(option.product.sale_price or 0).quantize(Decimal("0.01"))
        if option.product_id not in first_by_product:
            option.is_default = True
            first_by_product.add(option.product_id)
            option.product.package_type = packaging_type.name
            option.product.save(update_fields=["package_type", "updated_at"])
        option.save(
            update_fields=[
                "packaging_type",
                "cost_price",
                "sale_price",
                "is_default",
                "updated_at",
            ]
        )

        # A tabela intermediária do ManyToMany só recebe o índice único ao fim
        # desta migração. Sem este controle, duas opções da mesma categoria e
        # do mesmo tipo podem inserir pares duplicados antes de o índice existir.
        category_packaging_key = (option.product.category_id, packaging_type.pk)
        if category_packaging_key not in category_packaging_links:
            option.product.category.packaging_types.add(packaging_type)
            category_packaging_links.add(category_packaging_key)

    for item in StockEntryItem.objects.all().iterator():
        quantity = Decimal(item.quantity or 0)
        item.entry_unit_name = "Unidade"
        item.entry_quantity = max(int(quantity), 1)
        item.conversion_factor = 1
        item.purchase_price = Decimal(item.unit_cost or 0).quantize(Decimal("0.01"))
        item.save(
            update_fields=[
                "entry_unit_name",
                "entry_quantity",
                "conversion_factor",
                "purchase_price",
                "updated_at",
            ]
        )

    for item in StockOutputItem.objects.all().iterator():
        sale_quantity = max(int(item.sale_quantity or 1), 1)
        historical_total = Decimal(item.quantity or 0) * Decimal(item.unit_sale_price or 0)
        item.sale_price = (historical_total / sale_quantity).quantize(Decimal("0.01"))
        item.save(update_fields=["sale_price", "updated_at"])


def reverse_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0009_output_pos_checkout")]

    operations = [
        migrations.CreateModel(
            name="PackagingType",
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
                ("name", models.CharField(max_length=60, unique=True)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="category",
            name="packaging_types",
            field=models.ManyToManyField(
                blank=True,
                related_name="categories",
                to="inventory.packagingtype",
            ),
        ),
        migrations.AddField(
            model_name="productpackaging",
            name="packaging_type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_options",
                to="inventory.packagingtype",
            ),
        ),
        migrations.AddField(
            model_name="productpackaging",
            name="cost_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="productpackaging",
            name="sale_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="productpackaging",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="packaging",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="entry_items",
                to="inventory.productpackaging",
            ),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="entry_unit_name",
            field=models.CharField(default="Unidade", max_length=60),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="entry_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="conversion_factor",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="stockentryitem",
            name="purchase_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="stockoutputitem",
            name="sale_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(migrate_packaging_and_documents, reverse_data),
        migrations.AlterField(
            model_name="productpackaging",
            name="packaging_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_options",
                to="inventory.packagingtype",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="productpackaging",
            name="inv_product_packaging_name_uniq",
        ),
        migrations.RemoveConstraint(
            model_name="productpackaging",
            name="inv_product_packaging_units_gt_one",
        ),
        migrations.RemoveConstraint(
            model_name="stockentryitem",
            name="inv_entry_item_values_valid",
        ),
        migrations.RemoveConstraint(
            model_name="stockoutputitem",
            name="inv_output_item_values_valid",
        ),
        migrations.AddConstraint(
            model_name="productpackaging",
            constraint=models.UniqueConstraint(
                fields=("product", "packaging_type"),
                name="inv_product_packaging_type_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="productpackaging",
            constraint=models.UniqueConstraint(
                condition=Q(is_default=True),
                fields=("product",),
                name="inv_product_one_default_packaging",
            ),
        ),
        migrations.AddConstraint(
            model_name="productpackaging",
            constraint=models.CheckConstraint(
                condition=Q(
                    units_per_package__gt=1,
                    cost_price__gte=0,
                    sale_price__gte=0,
                ),
                name="inv_product_packaging_values_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockentryitem",
            constraint=models.CheckConstraint(
                condition=Q(
                    quantity__gt=0,
                    unit_cost__gte=0,
                    entry_quantity__gt=0,
                    conversion_factor__gt=0,
                    purchase_price__gte=0,
                ),
                name="inv_entry_item_packaging_values_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockoutputitem",
            constraint=models.CheckConstraint(
                condition=Q(
                    quantity__gt=0,
                    sale_quantity__gt=0,
                    conversion_factor__gt=0,
                    unit_sale_price__gte=0,
                    sale_price__gte=0,
                ),
                name="inv_output_item_values_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="packagingtype",
            index=models.Index(fields=["name"], name="inv_pack_type_name_idx"),
        ),
        migrations.AddConstraint(
            model_name="packagingtype",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                name="inv_pack_type_name_ci_uniq",
            ),
        ),
    ]
