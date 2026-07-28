from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ProductEntryOutputCleanupMigrationTests(TransactionTestCase):
    migrate_from = ("inventory", "0018_harden_alerts_and_notifications")
    migrate_to = ("inventory", "0019_clear_products_entries_outputs")

    @property
    def app(self):
        return "inventory"

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        User = get_user_model()
        user = User.objects.create_user(username="cleanup-user", password="safe-password")
        Category = old_apps.get_model(self.app, "Category")
        Supplier = old_apps.get_model(self.app, "Supplier")
        PackagingType = old_apps.get_model(self.app, "PackagingType")
        Product = old_apps.get_model(self.app, "Product")
        ProductSupplier = old_apps.get_model(self.app, "ProductSupplier")
        ProductPackaging = old_apps.get_model(self.app, "ProductPackaging")
        StockEntry = old_apps.get_model(self.app, "StockEntry")
        StockEntryItem = old_apps.get_model(self.app, "StockEntryItem")
        StockOutput = old_apps.get_model(self.app, "StockOutput")
        StockOutputItem = old_apps.get_model(self.app, "StockOutputItem")
        Alert = old_apps.get_model(self.app, "Alert")
        Notification = old_apps.get_model(self.app, "Notification")
        SystemSetting = old_apps.get_model(self.app, "SystemSetting")

        category = Category.objects.create(name="Categoria preservada", active=True)
        supplier = Supplier.objects.create(name="Fornecedor preservado", active=True)
        packaging_type = PackagingType.objects.create(
            name="Fardo preservado",
            kind="GROUPING",
            active=True,
        )
        product = Product.objects.create(
            code="CLEAN-001",
            name="Produto temporário",
            category=category,
            stock=Decimal("10"),
            minimum_stock=Decimal("2"),
            cost_price=Decimal("3.00"),
            sale_price=Decimal("5.00"),
            active=True,
        )
        ProductSupplier.objects.create(product=product, supplier=supplier)
        ProductPackaging.objects.create(
            product=product,
            packaging_type=packaging_type,
            units_per_package=6,
            sale_price=Decimal("25.00"),
            active=True,
        )
        entry = StockEntry.objects.create(supplier=supplier, user_id=user.pk)
        StockEntryItem.objects.create(
            entry=entry,
            product=product,
            entry_quantity=1,
            quantity=1,
            purchase_price=Decimal("3.00"),
            unit_cost=Decimal("3.00"),
        )
        output = StockOutput.objects.create(
            user_id=user.pk,
            reason="COMMERCIAL",
            customer_name="Cliente temporário",
            payment_method="ON_ACCOUNT",
            payment_due_date=timezone.localdate() + timedelta(days=1),
        )
        StockOutputItem.objects.create(
            output=output,
            product=product,
            sale_quantity=1,
            conversion_factor=1,
            quantity=1,
            unit_sale_price=Decimal("5.00"),
            sale_price=Decimal("5.00"),
        )
        alert = Alert.objects.create(
            type="LOW_STOCK",
            level="WARNING",
            product=product,
            message="Alerta temporário",
            active=True,
        )
        Notification.objects.create(
            user_id=user.pk,
            alert=alert,
            title="Aviso temporário",
            message="Aviso ligado ao produto",
            level="WARNING",
        )
        Notification.objects.create(
            user_id=user.pk,
            title="Evento preservado",
            message="Evento geral do sistema",
            level="INFO",
        )
        SystemSetting.objects.create(
            key="cleanup_test_setting",
            value="preservar",
            description="Configuração que deve permanecer",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_only_operational_product_data_is_removed(self):
        Category = self.apps.get_model(self.app, "Category")
        Supplier = self.apps.get_model(self.app, "Supplier")
        PackagingType = self.apps.get_model(self.app, "PackagingType")
        Product = self.apps.get_model(self.app, "Product")
        StockEntry = self.apps.get_model(self.app, "StockEntry")
        StockOutput = self.apps.get_model(self.app, "StockOutput")
        Notification = self.apps.get_model(self.app, "Notification")
        SystemSetting = self.apps.get_model(self.app, "SystemSetting")

        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(StockEntry.objects.count(), 0)
        self.assertEqual(StockOutput.objects.count(), 0)
        self.assertTrue(Category.objects.filter(name="Categoria preservada").exists())
        self.assertTrue(Supplier.objects.filter(name="Fornecedor preservado").exists())
        self.assertTrue(PackagingType.objects.filter(name="Fardo preservado").exists())
        self.assertTrue(SystemSetting.objects.filter(key="cleanup_test_setting").exists())
        self.assertTrue(Notification.objects.filter(title="Evento preservado").exists())
        self.assertFalse(Notification.objects.filter(title="Aviso temporário").exists())
