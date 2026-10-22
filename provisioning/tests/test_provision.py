import copy
import unittest

from provisioning.scripts.provision import (
    CATALOG,
    CHECKS,
    CONTRACT,
    EXAMPLE,
    load_json,
    plan,
    validate,
)


class ProvisioningFoundationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(CONTRACT)
        cls.catalog = load_json(CATALOG)
        cls.checks = load_json(CHECKS)

    def setUp(self):
        self.config = copy.deepcopy(load_json(EXAMPLE))

    def errors(self):
        return validate(self.config, self.contract, self.catalog, self.checks)

    def test_example_is_valid(self):
        self.assertEqual(self.errors(), [])

    def test_invalid_uuid_is_rejected(self):
        self.config["installation_key"] = "not-a-uuid"
        self.assertIn("installation_key must be a canonical UUID", self.errors())

    def test_invalid_slug_is_rejected(self):
        self.config["slug"] = "Cliente Com Espaços"
        self.assertTrue(any("slug must use" in error for error in self.errors()))

    def test_missing_public_domain_is_rejected(self):
        del self.config["domains"]["flow_api"]
        self.assertIn("Missing public domain: flow_api", self.errors())

    def test_duplicate_public_domain_is_rejected(self):
        self.config["domains"]["core_api"] = self.config["domains"]["crm_api"]
        self.assertTrue(any("Duplicate public domain" in error for error in self.errors()))

    def test_production_placeholder_is_rejected(self):
        self.config["environment"] = "production"
        self.assertTrue(any("unsafe for production" in error for error in self.errors()))
        self.assertTrue(any("example UUID" in error for error in self.errors()))

    def test_realistic_production_configuration_is_valid(self):
        self.config["environment"] = "production"
        self.config["installation_name"] = "Cliente Alfa"
        self.config["slug"] = "cliente-alfa"
        self.config["installation_key"] = "eb14dca5-d6ca-40e1-a124-b2f2fa13422a"
        self.config["domains"] = {
            key: f"https://{key.replace('_', '-')}.cliente-alfa.com.br"
            for key in self.config["domains"]
        }
        self.config["administrator"]["email"] = "admin@cliente-alfa.com.br"
        self.assertEqual(self.errors(), [])

    def test_plaintext_secret_is_rejected(self):
        self.config["secret_references"]["POSTGRES_PASSWORD"] = "actual-value"
        self.assertTrue(any("runtime reference" in error for error in self.errors()))

    def test_administrator_password_field_is_rejected(self):
        self.config["administrator"]["password"] = "actual-value"
        self.assertTrue(any("Unknown administrator field: password" in error for error in self.errors()))

    def test_plan_is_deterministic_and_does_not_print_secret_references(self):
        first = plan(self.config, self.catalog, self.checks)
        self.assertEqual(first, plan(self.config, self.catalog, self.checks))
        self.assertIn("INICIALIZAÇÃO", first)
        self.assertIn("RuntimeConfig.account", first)
        self.assertIn("artgenial.base v1", first)
        self.assertNotIn("runtime:POSTGRES_PASSWORD", first)

    def test_websocket_binding_and_upgrade_are_distinct(self):
        checks_by_id = {check["id"]: check for check in self.checks["checks"]}
        self.assertEqual(checks_by_id["vite_ws_url"]["kind"], "frontend_binding")
        self.assertEqual(checks_by_id["vite_ws_url"]["domain_key"], "crm_api")
        self.assertNotIn("path", checks_by_id["vite_ws_url"])
        self.assertEqual(checks_by_id["crm_websocket"]["kind"], "websocket_upgrade")
        self.assertEqual(checks_by_id["crm_websocket"]["domain_key"], "crm_api")
        self.assertEqual(checks_by_id["crm_websocket"]["path"], "/cable")

        lines = plan(self.config, self.catalog, self.checks).splitlines()
        binding = next(line for line in lines if "[VITE_WS_URL]" in line)
        upgrade = next(line for line in lines if "crm_websocket:" in line)
        self.assertIn("https://api.cliente.example.test (frontend_binding)", binding)
        self.assertNotIn("wss://", binding)
        self.assertNotIn("/cable", binding)
        self.assertIn("wss://api.cliente.example.test/cable (websocket_upgrade)", upgrade)

    def test_catalog_contains_all_compose_services(self):
        self.assertEqual(len(self.catalog["services"]), 14)
        self.assertEqual(set(self.config["required_services"]),
                         {service["name"] for service in self.catalog["services"]})


if __name__ == "__main__":
    unittest.main()
