from django.contrib import admin

from .models import (
    Alert,
    AuditLog,
    Category,
    InventoryCount,
    InventoryItem,
    Lot,
    Movement,
    Notification,
    Product,
    ProductSupplier,
    StockAdjustment,
    StockEntry,
    StockEntryItem,
    StockOutput,
    StockOutputItem,
    Supplier,
    SystemSetting,
    UserProfile,
)


class EntryItemInline(admin.TabularInline):
    model = StockEntryItem
    extra = 0


class OutputItemInline(admin.TabularInline):
    model = StockOutputItem
    extra = 0


class InventoryItemInline(admin.TabularInline):
    model = InventoryItem
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "stock", "minimum_stock", "cost_price", "active")
    list_filter = ("active", "category", "brand")
    search_fields = ("code", "sku", "barcode", "name", "brand")
    readonly_fields = ("stock", "created_at", "updated_at")


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ("number", "entry_date", "supplier", "status", "total_value", "user")
    list_filter = ("status", "supplier")
    search_fields = ("number", "invoice_number", "supplier__name")
    inlines = [EntryItemInline]


@admin.register(StockOutput)
class StockOutputAdmin(admin.ModelAdmin):
    list_display = ("number", "output_date", "reason", "status", "user")
    list_filter = ("status", "reason")
    search_fields = ("number", "notes")
    inlines = [OutputItemInline]


@admin.register(InventoryCount)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("number", "started_at", "status", "category", "user")
    list_filter = ("status", "category")
    inlines = [InventoryItemInline]


for model in [
    UserProfile,
    Category,
    Supplier,
    ProductSupplier,
    Lot,
    Movement,
    StockAdjustment,
    Alert,
    Notification,
    AuditLog,
    SystemSetting,
]:
    admin.site.register(model)

admin.site.site_header = "FP Estoque — Administração"
admin.site.site_title = "FP Estoque"
admin.site.index_title = "Controle interno do depósito"
