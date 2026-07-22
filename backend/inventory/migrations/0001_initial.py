from django.conf import settings
from django.db import migrations

from ._initial_ops_1 import OPERATIONS as OPS_1
from ._initial_ops_2 import OPERATIONS as OPS_2
from ._initial_ops_3 import OPERATIONS as OPS_3
from ._initial_ops_4 import OPERATIONS as OPS_4
from ._initial_ops_5 import OPERATIONS as OPS_5
from ._initial_ops_6 import OPERATIONS as OPS_6


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = OPS_1 + OPS_2 + OPS_3 + OPS_4 + OPS_5 + OPS_6
