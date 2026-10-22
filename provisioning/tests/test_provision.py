import copy
import json
import unittest

from provisioning.scripts.provision import (
    CATALOG,
    CHECKS,
    CONTRACT,
    DEPLOYMENT_VARIABLES,
    EXAMPLE,
    build_manifest,
    load_json,
    plan,
    validate,
    validate_deployment_catalog,
)


class ProvisioningFoundationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(CONTRACT)
        cls.catalog = load_json(CATALOG)
        cls.checks = load_json(CHECKS)
        cls.variables_catalog = load_json(DEPLOYMENT_VARIABLES)

    def setUp(self):
        self.config = copy.deepcopy(load_json(EXAMPLE))

    def errors(self):
        return validate(self.config, self.contract, self.catalog, self.checks)

    def manifest(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(validate_deployment_catalog(
            self.variables_catalog, self.contract, self.catalog, self.checks), [])
        return build_manifest(self.config, self.catalog, self.checks, self.variables_catalog)

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

    def test_manifest_is_deterministic_and_has_six_public_endpoints(self):
        first = json.dumps(self.manifest(), sort_keys=True, ensure_ascii=False)
        self.assertEqual(first, json.dumps(self.manifest(), sort_keys=True, ensure_ascii=False))
        data = json.loads(first)
        self.assertEqual(data["manifest_version"], 1)
        self.assertEqual(len(data["infrastructure"]), 14)
        self.assertEqual(set(data["public_endpoints"]), set(self.contract["required_domains"]))

    def test_infrastructure_keeps_private_services_and_host_ports_private(self):
        services = {item["name"]: item for item in self.manifest()["infrastructure"]}
        for name in ("postgres", "redis", "rabbitmq", "clickhouse", "evo-bot-runtime"):
            with self.subTest(service=name):
                self.assertFalse(services[name]["public_endpoint_required"])
                self.assertNotIn("domain", services[name])
                self.assertNotIn("domain_key", services[name])
        for item in services.values():
            self.assertNotIn("host_port", item)
            self.assertNotIn("host_ports", item)
            self.assertNotIn("ports", item)
        self.assertFalse(services["mailhog"]["commercial_email_solution"])

    def test_websocket_variable_is_http_origin_and_check_is_websocket_endpoint(self):
        data = self.manifest()
        variables = {item["name"]: item for item in data["variables"]["domain_binding"]}
        self.assertEqual(variables["VITE_WS_URL"]["value"], "https://api.cliente.example.test")
        self.assertNotIn("/cable", variables["VITE_WS_URL"]["value"])
        self.assertFalse(variables["VITE_WS_URL"]["value"].startswith("wss://"))
        checks = {item["id"]: item for item in data["validation"]}
        self.assertEqual(checks["crm_websocket"]["target"], "wss://api.cliente.example.test/cable")

    def test_secrets_are_only_runtime_references(self):
        data = self.manifest()
        secrets = data["variables"]["secret_reference"]
        self.assertEqual({item["name"] for item in secrets},
                         set(self.contract["required_secret_references"]) | {"AUTH_APIKEY_INTEGRATION_LOCAL"})
        self.assertTrue(all(item["reference"] == f"runtime:{item['name']}" for item in secrets))
        output = json.dumps(data)
        self.assertNotIn("actual-value", output)
        self.assertNotIn("password", data["installation"])
        self.assertNotIn("evoflow-dev-key", output)

    def test_invalid_secret_literal_cannot_pass_validation(self):
        self.config["secret_references"]["POSTGRES_PASSWORD"] = "actual-value"
        self.assertTrue(self.errors())

    def test_production_requires_integration_runtime_secret_and_no_dev_defaults(self):
        self.config["environment"] = "production"
        self.config["installation_name"] = "Cliente Alfa"
        self.config["slug"] = "cliente-alfa"
        self.config["installation_key"] = "eb14dca5-d6ca-40e1-a124-b2f2fa13422a"
        self.config["domains"] = {
            key: f"https://{key.replace('_', '-')}.cliente-alfa.com.br"
            for key in self.config["domains"]
        }
        self.config["administrator"]["email"] = "admin@cliente-alfa.com.br"
        data = self.manifest()
        secrets = {item["name"]: item for item in data["variables"]["secret_reference"]}
        self.assertTrue(secrets["AUTH_APIKEY_INTEGRATION_LOCAL"]["required"])
        self.assertEqual(secrets["AUTH_APIKEY_INTEGRATION_LOCAL"]["reference"],
                         "runtime:AUTH_APIKEY_INTEGRATION_LOCAL")
        settings = data["variables"]["environment_setting"]
        self.assertTrue(all(item["value"] is None for item in settings))
        self.assertTrue(any("commercial email" in item for item in data["delivery"]["pending_requirements"]))
        output = json.dumps(data)
        for unsafe in ("evoflow-dev-key", "evoai_dev_password", "evoai_redis_pass", "localhost", ".test"):
            self.assertNotIn(unsafe, output)

    def test_catalog_rejects_literal_or_unsafe_public_mapping(self):
        variables = copy.deepcopy(self.variables_catalog)
        variable = next(item for item in variables["variables"] if item["name"] == "AUTH_APIKEY_INTEGRATION_LOCAL")
        variable["source"]["value"] = "evoflow-dev-key"
        errors = validate_deployment_catalog(variables, self.contract, self.catalog, self.checks)
        self.assertTrue(any("unsupported mapping or literal value" in error for error in errors))
        services = copy.deepcopy(self.catalog)
        postgres = next(item for item in services["services"] if item["name"] == "postgres")
        postgres["public_endpoint_required"] = True
        self.assertTrue(any("must remain private" in error for error in
                            validate_deployment_catalog(self.variables_catalog, self.contract, services, self.checks)))

    def test_tinymce_optional_initialization_and_delivery_gate(self):
        data = self.manifest()
        self.assertEqual([item["name"] for item in data["variables"]["optional_integration"]],
                         ["VITE_TINYMCE_API_KEY"])
        self.assertFalse(data["variables"]["optional_integration"][0]["required"])
        steps = {item["id"]: item for item in data["initialization"]}
        self.assertEqual(steps["artgenial_base"]["template_key"], "artgenial.base")
        self.assertEqual(steps["artgenial_base"]["template_version"], "1")
        self.assertEqual(steps["artgenial_base"]["installation_key"], self.config["installation_key"])
        self.assertFalse(data["delivery"]["ready"])
        self.assertEqual(data["delivery"]["release_rule"], "all_required_checks_pass")
        self.assertEqual(set(data["delivery"]["required_check_ids"]),
                         {check["id"] for check in self.checks["checks"] if check["required"]})


if __name__ == "__main__":
    unittest.main()
