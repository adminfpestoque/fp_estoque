from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

OPERATIONS = [
    migrations.CreateModel(name='InventoryItem', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('system_quantity', models.DecimalField(decimal_places=3, max_digits=14)), ('counted_quantity', models.DecimalField(decimal_places=3, max_digits=14)), ('justification', models.TextField(blank=True)), ('adjusted', models.BooleanField(default=False)), ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inventory.inventorycount')), ('adjustment_movement', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inventory_item', to='inventory.movement')), ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inventory_items', to='inventory.product'))], options={'constraints': [models.UniqueConstraint(fields=('inventory', 'product'), name='inventory_inventoryitem_inventory_product_uniq'), models.CheckConstraint(condition=models.Q(('counted_quantity__gte', 0), ('system_quantity__gte', 0)), name='inventory_inventoryitem_quantities_nonnegative')]}),
    migrations.AddIndex(model_name='alert', index=models.Index(fields=['active', 'type'], name='inv_alert_active_type_idx')),
    migrations.AddConstraint(model_name='stockadjustment', constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0)), name='inv_adjustment_qty_valid')),
    migrations.AddConstraint(model_name='stockentryitem', constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0), ('unit_cost__gte', 0)), name='inv_entry_item_values_valid')),
    migrations.AddIndex(model_name='stockoutput', index=models.Index(fields=['status', 'output_date'], name='inv_output_status_date_idx')),
    migrations.AddIndex(model_name='movement', index=models.Index(fields=['-created_at'], name='inv_movement_created_idx')),
    migrations.AddIndex(model_name='movement', index=models.Index(fields=['type'], name='inv_movement_type_idx')),
    migrations.AddIndex(model_name='movement', index=models.Index(fields=['product', 'created_at'], name='inv_mov_prod_date_idx'))
]
