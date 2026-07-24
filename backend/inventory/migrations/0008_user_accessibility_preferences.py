from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_product_soft_delete_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="theme",
            field=models.CharField(
                choices=[
                    ("LIGHT", "Claro"),
                    ("DARK", "Escuro"),
                    ("HIGH_CONTRAST", "Alto contraste"),
                ],
                default="LIGHT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="font_scale",
            field=models.CharField(
                choices=[
                    ("NORMAL", "Padrão"),
                    ("LARGE", "Grande"),
                    ("EXTRA_LARGE", "Muito grande"),
                ],
                default="NORMAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="reduced_motion",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="enhanced_focus",
            field=models.BooleanField(default=True),
        ),
    ]
