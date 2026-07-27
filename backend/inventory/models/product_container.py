from django.db import models

from .catalog import PackagingType, Product


if not hasattr(Product, "packaging"):
    Product.add_to_class(
        "packaging",
        models.ForeignKey(
            PackagingType,
            on_delete=models.PROTECT,
            related_name="products",
            null=True,
            blank=True,
        ),
    )


if not getattr(Product, "_simple_packaging_installed", False):
    _original_save = Product.save

    def save_with_packaging(self, *args, **kwargs):
        changed_fields = set()
        if not self.packaging_id:
            default_packaging = (
                PackagingType.objects.filter(name__iexact="GARRAFA").first()
                or PackagingType.objects.filter(active=True).order_by("name").first()
            )
            if default_packaging is None:
                default_packaging = PackagingType.objects.create(
                    name="GARRAFA",
                    active=True,
                )
            self.packaging = default_packaging
            changed_fields.add("packaging")

        package_name = self.packaging.name if self.packaging_id else ""
        if self.package_type != package_name:
            self.package_type = package_name
            changed_fields.add("package_type")

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and changed_fields:
            kwargs["update_fields"] = list(set(update_fields) | changed_fields)
        return _original_save(self, *args, **kwargs)

    Product.save = save_with_packaging
    Product._simple_packaging_installed = True
