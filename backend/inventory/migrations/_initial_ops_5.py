from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

OPERATIONS = [
    migrations.AddConstraint(model_name='movement', constraint=models.CheckConstraint(condition=models.Q(('final_stock__gte', 0), ('previous_stock__gte', 0), ('quantity__gt', 0), ('unit_cost__gte', 0)), name='inventory_movement_quantities_valid')),
    migrations.AddConstraint(model_name='stockoutputitem', constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0)), name='inv_output_item_qty_valid')),
    migrations.AddIndex(model_name='stockentry', index=models.Index(fields=['status', 'entry_date'], name='inv_entry_status_date_idx')),
    migrations.AddConstraint(model_name='productsupplier', constraint=models.UniqueConstraint(fields=('product', 'supplier'), name='inv_product_supplier_uniq')),
    migrations.AddIndex(model_name='product', index=models.Index(fields=['name'], name='inv_product_name_idx')),
    migrations.AddIndex(model_name='product', index=models.Index(fields=['code'], name='inv_product_code_idx')),
    migrations.AddIndex(model_name='product', index=models.Index(fields=['barcode'], name='inv_product_barcode_idx')),
    migrations.AddConstraint(model_name='product', constraint=models.CheckConstraint(condition=models.Q(('cost_price__gte', 0), ('maximum_stock__gte', 0), ('minimum_stock__gte', 0), ('package_quantity__gt', 0), ('sale_price__gte', 0), ('stock__gte', 0)), name='inventory_product_nonnegative_values'))
]
