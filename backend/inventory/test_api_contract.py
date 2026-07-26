from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse


class ApiRouteContractTests(SimpleTestCase):
    CORE_COLLECTION_ROUTES = {
        "/api/users/": "users-list",
        "/api/categories/": "category-list",
        "/api/packaging-types/": "packaging-types-list",
        "/api/suppliers/": "suppliers-list",
        "/api/products/": "products-list",
        "/api/lots/": "lot-list",
        "/api/entries/": "stockentry-list",
        "/api/outputs/": "stockoutput-list",
        "/api/movements/": "movement-list",
        "/api/adjustments/": "stockadjustment-list",
        "/api/inventories/": "inventory-list",
        "/api/alerts/": "alert-list",
        "/api/notifications/": "notifications-list",
        "/api/audit-logs/": "auditlog-list",
        "/api/settings/": "systemsetting-list",
    }

    def test_frontend_collection_routes_are_registered(self):
        for path, expected_name in self.CORE_COLLECTION_ROUTES.items():
            with self.subTest(path=path):
                match = resolve(path)
                self.assertEqual(match.url_name, expected_name)

    def test_packaging_types_reverse_contract(self):
        self.assertEqual(reverse("packaging-types-list"), "/api/packaging-types/")

    def test_health_endpoint_identifies_current_api(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(
            response.json()["packaging_types_endpoint"],
            "/api/packaging-types/",
        )

    def test_packaging_types_endpoint_exists_and_requires_authentication(self):
        response = self.client.get("/api/packaging-types/")
        self.assertIn(response.status_code, {401, 403})
        self.assertNotEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_unknown_api_route_returns_safe_json_instead_of_debug_html(self):
        response = self.client.get("/api/route-that-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json()["status_code"], 404)
        self.assertNotIn("Traceback", response.content.decode("utf-8"))
