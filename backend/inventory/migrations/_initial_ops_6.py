from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

OPERATIONS = [
    migrations.AddIndex(model_name='lot', index=models.Index(fields=['expiration_date'], name='inv_lot_expiration_idx')),
    migrations.AddIndex(model_name='lot', index=models.Index(fields=['product', 'quantity'], name='inv_lot_prod_qty_idx')),
    migrations.AddConstraint(model_name='lot', constraint=models.CheckConstraint(condition=models.Q(('cost_price__gte', 0), ('quantity__gte', 0), ('received_quantity__gte', 0)), name='inventory_lot_values_nonnegative')),
    migrations.AlterUniqueTogether(name='lot', unique_together={('product', 'number')})
]
