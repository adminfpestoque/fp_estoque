from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]

    operations = [
        migrations.RunSQL(migrations.RunSQL.noop, migrations.RunSQL.noop),
    ]
