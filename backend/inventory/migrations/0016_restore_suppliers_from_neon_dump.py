from django.db import migrations


SUPPLIERS = [
    {
        "name": "AMBEV",
        "corporate_name": "",
        "document": "08562308000647",
        "state_registration": "",
        "contact_name": "",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "cep": "",
        "address": "",
        "address_number": "",
        "district": "",
        "city": "PAU DOS FERROS",
        "state": "RN",
        "notes": "",
        "active": True,
    },
    {
        "name": "SANTANENSE",
        "corporate_name": "",
        "document": "37297161000107",
        "state_registration": "",
        "contact_name": "",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "cep": "",
        "address": "",
        "address_number": "",
        "district": "",
        "city": "PAU DOS FERROS",
        "state": "RN",
        "notes": "",
        "active": True,
    },
    {
        "name": "SOLAR COCA COLA",
        "corporate_name": "",
        "document": "07196033002737",
        "state_registration": "",
        "contact_name": "",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "cep": "",
        "address": "",
        "address_number": "",
        "district": "",
        "city": "PAU DOS FERROS",
        "state": "RN",
        "notes": "",
        "active": True,
    },
    {
        "name": "SJM DISTRIBUIDORA",
        "corporate_name": "",
        "document": "29607155000253",
        "state_registration": "",
        "contact_name": "",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "cep": "",
        "address": "",
        "address_number": "",
        "district": "",
        "city": "PAU DOS FERROS",
        "state": "RN",
        "notes": "",
        "active": True,
    },
    {
        "name": "GRUPO PETROPOLIS",
        "corporate_name": "",
        "document": "16622166001232",
        "state_registration": "",
        "contact_name": "",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "cep": "",
        "address": "",
        "address_number": "",
        "district": "",
        "city": "MOSSORO",
        "state": "RN",
        "notes": "",
        "active": True,
    },
]


def restore_suppliers(apps, schema_editor):
    Supplier = apps.get_model("inventory", "Supplier")

    for supplier_data in SUPPLIERS:
        document = supplier_data["document"]
        defaults = {
            key: value
            for key, value in supplier_data.items()
            if key != "document"
        }
        Supplier.objects.update_or_create(
            document=document,
            defaults=defaults,
        )


def noop_reverse(apps, schema_editor):
    # A reversão não apaga fornecedores para evitar perda acidental de dados.
    pass


class Migration(migrations.Migration):
    dependencies = [("inventory", "0015_reset_inventory_and_add_product_packaging")]

    operations = [
        migrations.RunPython(restore_suppliers, noop_reverse),
    ]
