from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .base import TimeStamped

class Category(TimeStamped):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(TimeStamped):
    name = models.CharField(max_length=180)
    corporate_name = models.CharField(max_length=180, blank=True)
    document = models.CharField(max_length=20, unique=True, blank=True, null=True)
    state_registration = models.CharField(max_length=30, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    cep = models.CharField(max_length=10, blank=True)
    address = models.CharField(max_length=180, blank=True)
    address_number = models.CharField(max_length=20, blank=True)
    district = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"], name="inv_supplier_name_idx")]

    def __str__(self):
        return self.name


class Product(TimeStamped):
    VOLUME_ML = "ML"
    VOLUME_L = "L"
    VOLUME_UNITS = [
        (VOLUME_ML, "Mililitros (ML)"),
        (VOLUME_L, "Litros (L)"),
    ]

    code = models.CharField(max_length=50, unique=True)
    sku = models.CharField(max_length=80, unique=True, blank=True, null=True)
    barcode = models.CharField(max_length=80, unique=True, blank=True, null=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_products",
    )
    brand = models.CharField(max_length=100, blank=True)
    package_type = models.CharField(max_length=60, blank=True)
    volume = models.PositiveIntegerField(null=True, blank=True)
    volume_unit = models.CharField(max_length=2, choices=VOLUME_UNITS, default=VOLUME_ML)
    unit = models.CharField(max_length=20, default="UN")
    package_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=1
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    maximum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    location = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deleted_products",
    )
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="inv_product_name_idx"),
            models.Index(fields=["code"], name="inv_product_code_idx"),
            models.Index(fields=["barcode"], name="inv_product_barcode_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    cost_price__gte=0,
                    sale_price__gte=0,
                    stock__gte=0,
                    minimum_stock__gte=0,
                    maximum_stock__gte=0,
                    package_quantity__gt=0,
                ),
                name="inventory_product_nonnegative_values",
            )
        ]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_status(self):
        if self.is_deleted:
            return "Excluído"
        return "Ativo" if self.active else "Inativo"

    @property
    def package_description(self):
        measurement = f"{self.volume}{self.volume_unit}" if self.volume else ""
        return " ".join(part for part in [self.package_type.strip(), measurement] if part)

    @property
    def low_stock(self):
        return self.stock <= self.minimum_stock

    @property
    def stock_value(self):
        return self.stock * self.cost_price

    def __str__(self):
        return self.name


class ProductPackaging(TimeStamped):
    """Formas de retirada configuradas por produto.

    O estoque continua armazenado em unidades. Esta tabela informa quantas
    unidades existem em uma caixa, fardo, grade ou outra apresentação usada
    no caixa.
    """

    BOX = "BOX"
    BUNDLE = "BUNDLE"
    CRATE = "CRATE"
    PACK = "PACK"
    TRAY = "TRAY"
    BAG = "BAG"
    OTHER = "OTHER"
    TYPES = [
        (BOX, "Caixa"),
        (BUNDLE, "Fardo"),
        (CRATE, "Grade/engradado"),
        (PACK, "Pacote"),
        (TRAY, "Bandeja"),
        (BAG, "Saco"),
        (OTHER, "Outra"),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="packaging_options",
    )
    type = models.CharField(max_length=16, choices=TYPES, default=BOX)
    name = models.CharField(max_length=50)
    units_per_package = models.PositiveIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["units_per_package", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"],
                name="inv_product_packaging_name_uniq",
            ),
            models.CheckConstraint(
                condition=Q(units_per_package__gt=1),
                name="inv_product_packaging_units_gt_one",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or self.get_type_display()).strip().split())
        if self.units_per_package <= 1:
            raise ValidationError("Uma embalagem deve conter pelo menos 2 unidades.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — {self.name} ({self.units_per_package} UN)"


class ProductSupplier(TimeStamped):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="supplier_links")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="product_links")
    is_primary = models.BooleanField(default=False)
    last_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "supplier"], name="inv_product_supplier_uniq"
            )
        ]


class Lot(TimeStamped):
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lots",
    )
    product_name_snapshot = models.CharField(max_length=180, blank=True)
    product_code_snapshot = models.CharField(max_length=50, blank=True)
    number = models.CharField(max_length=80)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    entry_date = models.DateField(default=timezone.localdate)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="lots"
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("product", "number")
        ordering = [F("expiration_date").asc(nulls_last=True), "created_at"]
        indexes = [
            models.Index(fields=["expiration_date"], name="inv_lot_expiration_idx"),
            models.Index(fields=["product", "quantity"], name="inv_lot_prod_qty_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=0, received_quantity__gte=0, cost_price__gte=0),
                name="inventory_lot_values_nonnegative",
            )
        ]

    def save(self, *args, **kwargs):
        if self.product_id:
            self.product_name_snapshot = self.product.name
            self.product_code_snapshot = self.product.code
        super().save(*args, **kwargs)

    @property
    def product_name(self):
        return self.product.name if self.product_id else self.product_name_snapshot

    @property
    def product_code(self):
        return self.product.code if self.product_id else self.product_code_snapshot

    @property
    def expired(self):
        return bool(self.expiration_date and self.expiration_date < timezone.localdate())

    @property
    def status(self):
        if not self.active:
            return "INACTIVE"
        if self.quantity <= 0:
            return "EMPTY"
        if self.expired:
            return "EXPIRED"
        return "AVAILABLE"

    def __str__(self):
        return f"{self.product_name or 'Produto excluído'} — lote {self.number}"


