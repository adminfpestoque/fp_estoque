from django.db import models

from .catalog import PackagingType, Product


if not getattr(PackagingType, "_idempotent_names_installed", False):
    _original_packaging_save = PackagingType.save

    def save_packaging_without_case_duplicates(self, *args, **kwargs):
        normalized = " ".join(str(self.name or "").strip().split())
        if self._state.adding and normalized:
            existing = PackagingType.objects.filter(name__iexact=normalized).first()
            if existing:
                self.pk = existing.pk
                self.name = existing.name
                self.active = existing.active
                if hasattr(existing, "created_at"):
                    self.created_at = existing.created_at
                if hasattr(existing, "updated_at"):
                    self.updated_at = existing.updated_at
                self._state.adding = False
                self._state.db = existing._state.db
                return None
        return _original_packaging_save(self, *args, **kwargs)

    PackagingType.save = save_packaging_without_case_duplicates
    PackagingType._idempotent_names_installed = True


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
                PackagingType.objects.filter(name__iexact="Garrafa").first()
                or PackagingType.objects.filter(active=True).order_by("name").first()
            )
            if default_packaging is None:
                default_packaging = PackagingType.objects.create(
                    name="Garrafa",
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
