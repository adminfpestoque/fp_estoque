from decimal import Decimal

from django.core.management.base import BaseCommand

from inventory.models import Category, Product, Supplier, SystemSetting


class Command(BaseCommand):
    help = "Cria dados de exemplo seguros para validar o sistema."

    def handle(self, *args, **options):
        categories = {}
        for name in ["Cervejas", "Refrigerantes", "Energéticos", "Sucos", "Águas", "Destilados", "Vinhos", "Gelo", "Outros"]:
            categories[name], _ = Category.objects.get_or_create(name=name)
        supplier, _ = Supplier.objects.get_or_create(
            document="00000000000191",
            defaults={"name": "Fornecedor de Demonstração", "corporate_name": "Fornecedor de Demonstração LTDA", "active": True},
        )
        examples = [
            ("FP-001", "Cerveja Pilsen 350 ml", "Cervejas", "Lata", Decimal("3.10"), Decimal("4.50"), Decimal("24"), Decimal("12")),
            ("FP-002", "Refrigerante Cola 2 L", "Refrigerantes", "Garrafa PET", Decimal("7.50"), Decimal("10.00"), Decimal("10"), Decimal("8")),
            ("FP-003", "Água mineral 500 ml", "Águas", "Garrafa PET", Decimal("1.20"), Decimal("2.50"), Decimal("30"), Decimal("15")),
        ]
        for code, name, category, package, cost, sale, stock, minimum in examples:
            Product.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": categories[category],
                    "supplier": supplier,
                    "package_type": package,
                    "cost_price": cost,
                    "sale_price": sale,
                    "stock": stock,
                    "minimum_stock": minimum,
                    "maximum_stock": stock * 4,
                    "active": True,
                },
            )
        SystemSetting.objects.update_or_create(key="expiration_alert_days", defaults={"value": "30", "description": "Dias de antecedência para alertas de validade."})
        SystemSetting.objects.update_or_create(key="low_movement_days", defaults={"value": "30", "description": "Dias sem movimentação para relatório de baixa movimentação."})
        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados/atualizados com sucesso."))
