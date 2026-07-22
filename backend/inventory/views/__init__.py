from .alerts import AlertViewSet, AuditLogViewSet, NotificationViewSet, SystemSettingViewSet
from .catalog import CategoryViewSet, LotViewSet, ProductViewSet, SupplierViewSet, UserViewSet
from .dashboard import dashboard
from .documents import MovementViewSet, StockAdjustmentViewSet, StockEntryViewSet, StockOutputViewSet
from .inventories import InventoryViewSet
from .misc import forgot_password, report_catalog, report_export, report_preview, reset_password, upload_product_image
from .reporting import report_xlsx_export

__all__ = [
    name
    for name in globals()
    if name.endswith("ViewSet")
    or name
    in {
        "dashboard",
        "forgot_password",
        "report_catalog",
        "report_export",
        "report_preview",
        "report_xlsx_export",
        "reset_password",
        "upload_product_image",
    }
]
