from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from .base import TimeStamped


class PackagingType(TimeStamped):
    """Catálogo usado para a embalagem do produto e para o tipo de empacotamento."""

    CONTAINER = "CONTAINER"
    GROUPING = "GROUPING"
    BOTH = "BOTH"
    KIND_CHOICES = [
        (CONTAINER, "Embalagem do produto"),
        (GROUPING, "Tipo de empacotamento"),
        (BOTH, "Ambos"),
    ]

    name = models.CharField(max_length=60, unique=True)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=GROUPING)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"], name="inv_pack_type_name_idx")]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="inv_pack_type_name_ci_uniq",
            )
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").strip().split())
        if not self.name:
            raise ValidationError("Informe o nome da embalagem ou do tipo de empacotamento.")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.name


class Product(TimeStamped):
    UNIT = "UN"
    UNIT_CHOICES = [(UNIT, "Unidade")]
    VOLUME_ML = "ML"
    VOLUME_L = "L"
    VOLUME_UNIT_CHOICES = [(VOLUME_ML, "Mililitros"), (VOLUME_L, "Litros")]

    code = models.CharField(max_length=50, unique=True)
    sku = models.CharField(max_length=80, unique=True, blank=True, null=True)
    barcode = models.CharField(max_length=80, unique=True, blank=True, null=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES, default=UNIT)
    package_type = models.CharField(max_length=80, blank=True)
    package_quantity = models.PositiveIntegerField(default=1)
    volume = models.PositiveIntegerField(default=1)
    volume_unit = models.CharField(max_length=2, choices=VOLUME_UNIT_CHOICES, default=VOLUME_ML)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    location = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_products",
    )
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    cost_price__gte=0,
                    sale_price__gte=0,
                    stock__gte=0,
                    minimum_stock__gte=0,
                    package_quantity__gt=0,
                ),
                name="inventory_product_nonnegative_values",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def low_stock(self):
        return self.stock <= self.minimum_stock

    @property
    def stock_value(self):
        return self.stock * self.cost_price

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
        default_option = self.packaging_options.filter(active=True, is_default=True).first()
        if default_option:
            return default_option.display_name
        return self.package_type or self.unit


class ProductSupplier(TimeStamped):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="supplier_links")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="product_links")
    supplier_code = models.CharField(max_length=80, blank=True)
    last_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preferred = models.BooleanField(default=False)

    class Meta:
        ordering = ["-preferred", "supplier__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "supplier"],
                name="inventory_product_supplier_unique",
            )
        ]

    def __str__(self):
        return f"{self.product} - {self.supplier}"


class ProductPackaging(TimeStamped):
    BOX = "BOX"
    BUNDLE = "BUNDLE"
    CRATE = "CRATE"
    PACK = "PACK"
    TRAY = "TRAY"
    BAG = "BAG"
    OTHER = "OTHER"
    TYPE_CHOICES = [
        (BOX, "Caixa"),
        (BUNDLE, "Fardo"),
        (CRATE, "Grade/engradado"),
        (PACK, "Pacote"),
        (TRAY, "Bandeja"),
        (BAG, "Saco"),
        (OTHER, "Outra"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="packaging_options")
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=12, choices=TYPE_CHOICES, default=OTHER)
    packaging_type = models.ForeignKey(
        PackagingType,
        on_delete=models.PROTECT,
        related_name="product_options",
    )
    units_per_package = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product", "-is_default", "packaging_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "packaging_type"],
                name="inv_product_packaging_type_uniq",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_default=True),
                name="inv_product_one_default_packaging",
            ),
            models.CheckConstraint(
                condition=Q(
                    units_per_package__gt=1,
                    cost_price__gte=0,
                    sale_price__gte=0,
                ),
                name="inv_product_packaging_values_valid",
            ),
        ]

    @classmethod
    def resolve_packaging_type(cls, value):
        if isinstance(value, PackagingType):
            return value
        if value is None:
            return None
        if isinstance(value, int) or str(value).isdigit():
            return PackagingType.objects.filter(pk=int(value)).first()
        name = " ".join(str(value).strip().split())
        if not name:
            return None
        existing = PackagingType.objects.filter(name__iexact=name).first()
        if existing:
            return existing
        return PackagingType.objects.create(name=name)

    def save(self, *args, **kwargs):
        if not self.packaging_type_id:
            self.packaging_type = self.resolve_packaging_type(self.name or self.get_type_display())
        self.name = self.packaging_type.name
        self.type = self.OTHER
        if self.units_per_package < 2:
            raise ValidationError("A embalagem deve possuir pelo menos 2 unidades.")
        super().save(*args, **kwargs)

    @property
    def type_display(self):
        return self.packaging_type.name

    @property
    def display_name(self):
        return f"{self.packaging_type.name} com {self.units_per_package} unidades"

    @property
    def total_cost(self):
        return self.cost_price

    @property
    def total_sale_price(self):
        return self.sale_price


class Lot(TimeStamped):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="lots")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="lots", null=True, blank=True)
    entry = models.ForeignKey("StockEntry", on_delete=models.SET_NULL, related_name="lots", null=True, blank=True)
    lot_number = models.CharField(max_length=100)
    manufacturing_date = models.DateField(blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["expiration_date", "lot_number"]
        constraints = [
            models.UniqueConstraint(fields=["product", "lot_number"], name="inventory_lot_product_number_unique"),
            models.CheckConstraint(condition=Q(quantity__gte=0, received_quantity__gte=0, cost_price__gte=0), name="inventory_lot_nonnegative_values"),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.lot_number}"

    @property
    def product_name(self):
        return self.product.name

    @property
    def product_code(self):
        return self.product.code

    @property
    def status(self):
        if self.quantity <= 0:
            return "EMPTY"
        if self.expiration_date and self.expiration_date < timezone.localdate():
            return "EXPIRED"
        if self.expiration_date and self.expiration_date <= timezone.localdate() + timezone.timedelta(days=30):
            return "NEAR_EXPIRY"
        return "AVAILABLE"

    @property
    def expired(self):
        return bool(self.expiration_date and self.expiration_date < timezone.localdate())
