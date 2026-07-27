from django.db import migrations, models


CONTAINER_NAMES = {
    "lata",
    "garrafa",
    "garrafa pet",
    "garrafa long neck",
    "garrafa retornável",
    "garrafa piriguete",
}

GROUPING_NAMES = [
    "Caixa",
    "Fardo",
    "Grade/engradado",
    "Pacote",
    "Bandeja",
    "Saco",
    "Outra",
]


def classify_and_seed_packaging_types(apps, schema_editor):
    PackagingType = apps.get_model("inventory", "PackagingType")

    for packaging in PackagingType.objects.all():
        normalized = " ".join(str(packaging.name or "").strip().casefold().split())
        if normalized == "pacote":
            kind = "BOTH"
        elif normalized in CONTAINER_NAMES:
            kind = "CONTAINER"
        else:
            kind = "GROUPING"
        if packaging.kind != kind:
            packaging.kind = kind
            packaging.save(update_fields=["kind", "updated_at"])

    for name in GROUPING_NAMES:
        existing = PackagingType.objects.filter(name__iexact=name).first()
        if existing:
            expected_kind = "BOTH" if name.casefold() == "pacote" else "GROUPING"
            updates = []
            if existing.kind != expected_kind:
                existing.kind = expected_kind
                updates.append("kind")
            if not existing.active:
                existing.active = True
                updates.append("active")
            if updates:
                updates.append("updated_at")
                existing.save(update_fields=updates)
        else:
            PackagingType.objects.create(
                name=name,
                kind="BOTH" if name.casefold() == "pacote" else "GROUPING",
                active=True,
            )


def reverse_classification(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0016_restore_suppliers_from_neon_dump")]

    operations = [
        migrations.AddField(
            model_name="packagingtype",
            name="kind",
            field=models.CharField(
                choices=[
                    ("CONTAINER", "Embalagem do produto"),
                    ("GROUPING", "Tipo de empacotamento"),
                    ("BOTH", "Ambos"),
                ],
                default="GROUPING",
                max_length=12,
            ),
        ),
        migrations.RunPython(
            classify_and_seed_packaging_types,
            reverse_classification,
        ),
    ]
