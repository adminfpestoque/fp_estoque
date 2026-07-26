from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path, old, new):
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado em {relative_path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/inventory/test_unified_packaging.py",
    "        self.category.packaging_types.add(self.package_type)\n",
    "",
)
replace_once(
    "backend/inventory/test_unified_packaging.py",
    '''    def test_product_and_category_share_the_same_packaging_type_catalog(self):
        box_type = self.client.post(
            "/api/packaging-types/",
            {"name": "Caixa térmica", "active": True},
            format="json",
        )
        self.assertEqual(box_type.status_code, 201, box_type.data)

        category = self.client.patch(
            f"/api/categories/{self.category.id}/",
            {"packaging_types": [self.package_type.id, box_type.data["id"]]},
            format="json",
        )
        self.assertEqual(category.status_code, 200, category.data)
        self.assertIn("Caixa térmica", category.data["packaging_type_names"])

        product = self.client.patch(
            f"/api/products/{self.product.id}/",
            {
                "packaging_options": [
                    {
                        "id": self.package.id,
                        "packaging_type": self.package_type.id,
                        "units_per_package": 12,
                        "cost_price": "30,00",
                        "sale_price": "5,00",
                        "is_default": True,
                        "active": True,
                    },
                    {
                        "packaging_type": box_type.data["id"],
                        "units_per_package": 24,
                        "cost_price": "55,00",
                        "sale_price": "9,00",
                        "is_default": False,
                        "active": True,
                    },
                ]
            },
            format="json",
        )
        self.assertEqual(product.status_code, 200, product.data)
        names = {item["packaging_type_name"] for item in product.data["packaging_options"]}
        self.assertEqual(names, {"Pacote", "Caixa térmica"})

        types = self.client.get("/api/packaging-types/?page_size=500")
        self.assertEqual(types.status_code, 200)
        rows = types.data.get("results", types.data)
        self.assertTrue(any(row["name"] == "Caixa térmica" for row in rows))
''',
    '''    def test_packaging_type_catalog_is_used_only_by_products(self):
        box_type = self.client.post(
            "/api/packaging-types/",
            {"name": "Caixa térmica", "active": True},
            format="json",
        )
        self.assertEqual(box_type.status_code, 201, box_type.data)

        category = self.client.patch(
            f"/api/categories/{self.category.id}/",
            {"name": "Gelo e bebidas geladas", "description": "Categoria sem vínculo com embalagem."},
            format="json",
        )
        self.assertEqual(category.status_code, 200, category.data)
        self.assertNotIn("packaging_types", category.data)
        self.assertNotIn("packaging_type_names", category.data)

        product = self.client.patch(
            f"/api/products/{self.product.id}/",
            {
                "packaging_options": [
                    {
                        "packaging_type": box_type.data["id"],
                        "units_per_package": 24,
                        "cost_price": "55,00",
                        "sale_price": "9,00",
                        "is_default": True,
                        "active": True,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(product.status_code, 200, product.data)
        self.assertEqual(len(product.data["packaging_options"]), 1)
        self.assertEqual(product.data["packaging_options"][0]["packaging_type_name"], "Caixa térmica")

        types = self.client.get("/api/packaging-types/?page_size=500")
        self.assertEqual(types.status_code, 200)
        rows = types.data.get("results", types.data)
        self.assertTrue(any(row["name"] == "Caixa térmica" for row in rows))
''',
)

replace_once(
    "backend/inventory/test_output_checkout.py",
    '''                "packaging_options": [
                    {
                        "id": self.box.id,
                        "type": ProductPackaging.BOX,
                        "name": "Caixa",
                        "units_per_package": 12,
                        "cost_price": "48,00",
                        "sale_price": "60,00",
                        "is_default": True,
                        "active": True,
                    },
                    {
                        "type": ProductPackaging.BUNDLE,
                        "name": "Fardo",
                        "units_per_package": 6,
                        "cost_price": "24,00",
                        "sale_price": "32,00",
                        "is_default": False,
                        "active": True,
                    },
                ]
''',
    '''                "packaging_options": [
                    {
                        "id": self.box.id,
                        "type": ProductPackaging.BOX,
                        "name": "Caixa",
                        "units_per_package": 12,
                        "cost_price": "48,00",
                        "sale_price": "60,00",
                        "is_default": True,
                        "active": True,
                    }
                ]
''',
)
replace_once(
    "backend/inventory/test_output_checkout.py",
    '''        options = {item["name"]: item for item in response.data["packaging_options"]}
        self.assertEqual(options["Caixa"]["units_per_package"], 12)
        self.assertEqual(options["Fardo"]["units_per_package"], 6)
        self.assertFalse(ProductPackaging.objects.filter(pk=self.crate.pk).exists())
''',
    '''        self.assertEqual(len(response.data["packaging_options"]), 1)
        option = response.data["packaging_options"][0]
        self.assertEqual(option["name"], "Caixa")
        self.assertEqual(option["units_per_package"], 12)
        self.assertFalse(ProductPackaging.objects.filter(pk=self.crate.pk).exists())
''',
)
