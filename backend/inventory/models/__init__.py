from .alerts import Alert, AuditLog, Notification, SystemSetting
from .catalog import Category, Lot, PackagingType, Product, ProductPackaging, ProductSupplier, Supplier
from .entry import StockEntry, StockEntryItem
from .movement import Movement
from .output import StockOutput, StockOutputItem
from .adjustment import StockAdjustment
from .counts import InventoryCount, InventoryItem
from .users import UserProfile
from ..maximum_stock_retired import retire_product_maximum_stock

retire_product_maximum_stock(Product)

__all__ = [
    "Alert", "AuditLog", "Category", "InventoryCount", "InventoryItem", "Lot",
    "Movement", "Notification", "PackagingType", "Product", "ProductPackaging", "ProductSupplier", "StockAdjustment",
    "StockEntry", "StockEntryItem", "StockOutput", "StockOutputItem", "Supplier",
    "SystemSetting", "UserProfile",
]
