from .catalog import CategorySerializer, LotSerializer, PackagingTypeSerializer, ProductSerializer, ProductPackagingSerializer, ProductSupplierSerializer, SupplierSerializer
from .documents import (MovementSerializer, StockAdjustmentSerializer, StockEntryItemSerializer, StockEntrySerializer, StockOutputItemSerializer, StockOutputSerializer)
from .misc import AlertSerializer, AuditLogSerializer, InventoryItemSerializer, InventorySerializer, NotificationSerializer, SystemSettingSerializer
from .users import MeSerializer, UserProfileSerializer, UserSerializer
from ..maximum_stock_retired import retire_product_serializer

retire_product_serializer(ProductSerializer)

__all__ = [name for name in globals() if name.endswith("Serializer")]
