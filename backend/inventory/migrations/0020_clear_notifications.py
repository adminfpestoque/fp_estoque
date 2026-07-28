from django.db import migrations


def clear_notifications(apps, schema_editor):
    Notification = apps.get_model("inventory", "Notification")
    Notification.objects.using(schema_editor.connection.alias).all().delete()


def reverse_noop(apps, schema_editor):
    # Exclusão de dados não possui reversão automática segura.
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0019_clear_products_entries_outputs")]

    operations = [
        migrations.RunPython(clear_notifications, reverse_noop),
    ]
