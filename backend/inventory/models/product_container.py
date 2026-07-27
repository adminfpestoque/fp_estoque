from django.db import models

from .catalog import PackagingType, Product


if not hasattr(Product, "packaging"):
    Product.add_to_class(
        "packaging",
        models.ForeignKey(
            PackagingType,
            on_delete=models.PROTECT,
            related_name="products",
        ),
    )


if not getattr(Product, "_simple_packaging_installed", False):
    _original_save = Product.save

    def save_with_packaging(self, *args, **kwargs):
        package_name = self.packaging.name if self.packaging_id else ""
        if self.package_type != package_name:
            self.package_type = package_name
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list(set(update_fields) | {"package_type"})
        return _original_save(self, *args, **kwargs)

    Product.save = save_with_packaging
    Product._simple_packaging_installed = True
