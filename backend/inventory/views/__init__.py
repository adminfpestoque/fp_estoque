from .alerts import AlertViewSet, AuditLogViewSet, NotificationViewSet, SystemSettingViewSet
from .catalog import CategoryViewSet, LotViewSet, PackagingTypeViewSet, ProductViewSet, SupplierViewSet, UserViewSet
from . import category_delete as _category_delete  # noqa: F401 — habilita exclusão segura de categorias
from . import supplier_delete as _supplier_delete  # noqa: F401 — habilita exclusão segura de fornecedores
from . import supplier_cep as _supplier_cep  # noqa: F401 — consulta CEP pelo endereço do fornecedor
from . import product_container as _product_container  # noqa: F401 — integra embalagem simples aos produtos
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
