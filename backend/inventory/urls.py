from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertViewSet,
    AuditLogViewSet,
    CategoryViewSet,
    InventoryViewSet,
    LotViewSet,
    MovementViewSet,
    NotificationViewSet,
    ProductViewSet,
    StockAdjustmentViewSet,
    StockEntryViewSet,
    StockOutputViewSet,
    SupplierViewSet,
    SystemSettingViewSet,
    UserViewSet,
    dashboard,
    forgot_password,
    report_catalog,
    report_export,
    report_preview,
    report_xlsx_export,
    reset_password,
    upload_product_image,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")
router.register("categories", CategoryViewSet)
router.register("suppliers", SupplierViewSet, basename="suppliers")
router.register("products", ProductViewSet, basename="products")
router.register("lots", LotViewSet)
router.register("entries", StockEntryViewSet)
router.register("outputs", StockOutputViewSet)
router.register("movements", MovementViewSet)
router.register("adjustments", StockAdjustmentViewSet)
router.register("inventories", InventoryViewSet)
router.register("alerts", AlertViewSet)
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("audit-logs", AuditLogViewSet)
router.register("settings", SystemSettingViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", dashboard, name="dashboard"),
    path("auth/forgot-password/", forgot_password, name="forgot-password"),
    path("auth/reset-password/", reset_password, name="reset-password"),
    path("uploads/product-image/", upload_product_image, name="product-image-upload"),
    path("reports/", report_catalog, name="report-catalog"),
    path("reports/preview/", report_preview, name="report-preview"),
    path("reports/export.pdf", report_export, {"export_format": "pdf"}, name="report-pdf"),
    path("reports/export.xlsx", report_xlsx_export, name="report-xlsx"),
    path("reports/export.csv", report_export, {"export_format": "csv"}, name="report-csv"),
    path("reports/daily.pdf", report_export, {"export_format": "pdf"}, name="daily-report-pdf"),
    path("reports/daily.xlsx", report_xlsx_export, name="daily-report-xlsx"),
    path("reports/daily.csv", report_export, {"export_format": "csv"}, name="daily-report-csv"),
]
