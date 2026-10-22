import copy
import json
import unittest

from provisioning.scripts.provision import (
    CATALOG,
    CHECKS,
    COMMERCIAL_RUNTIME,
    CONTRACT,
    DEPLOYMENT_VARIABLES,
    EXAMPLE,
    ConfigurationError,
    _commercial_database,
    build_manifest,
    load_json,
    plan,
    validate,
    validate_commercial_policy,
    validate_deployment_catalog,
)


class ProvisioningFoundationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(CONTRACT)
        cls.catalog = load_json(CATALOG)
        cls.checks = load_json(CHECKS)
        cls.variables_catalog = load_json(DEPLOYMENT_VARIABLES)
        cls.commercial_policy = load_json(COMMERCIAL_RUNTIME)

    def setUp(self):
        self.config = copy.deepcopy(load_json(EXAMPLE))

    def errors(self):
        return validate(self.config, self.contract, self.catalog, self.checks)

    def manifest(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(validate_deployment_catalog(
            self.variables_catalog, self.contract, self.catalog, self.checks), [])
        policy = self.commercial_policy if self.config["environment"] == "production" else None
        return build_manifest(self.config, self.catalog, self.checks, self.variables_catalog, policy)

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
        self.assertTrue(all(item["value"] is not None for item in settings))
        self.assertTrue(all(item["status"] == "resolved_by_commercial_policy" for item in settings))
        self.assertFalse(any("runtime setting" in item for item in data["delivery"]["pending_requirements"]))
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

    def test_commercial_policy_is_valid_and_deterministic(self):
        self.assertEqual(validate_commercial_policy(self.commercial_policy), [])
        self.assertEqual(self.commercial_policy, load_json(COMMERCIAL_RUNTIME))
        self.assertEqual(set(self.commercial_policy["settings"]),
                         {item["name"] for item in self.variables_catalog["variables"]
                          if item["classification"] == "environment_setting"})
        self.assertFalse(any("SECRET" in name or "PASSWORD" in name or "TOKEN" in name
                             for name in self.commercial_policy["settings"]))

    def test_commercial_policy_rejects_unknown_missing_and_secret_fields(self):
        policy = copy.deepcopy(self.commercial_policy)
        policy["unknown"] = "value"
        self.assertTrue(validate_commercial_policy(policy))
        policy = copy.deepcopy(self.commercial_policy)
        del policy["settings"]["DEBUG"]
        self.assertTrue(validate_commercial_policy(policy))
        policy = copy.deepcopy(self.commercial_policy)
        policy["settings"]["POSTGRES_PASSWORD"] = {"kind": "fixed", "value": "literal"}
        self.assertTrue(validate_commercial_policy(policy))
        policy = copy.deepcopy(self.commercial_policy)
        policy["settings"]["RAILS_ENV"]["password"] = "literal"
        self.assertTrue(validate_commercial_policy(policy))

    def test_commercial_policy_rejects_unsafe_or_development_values(self):
        for name, value in (
            ("RAILS_ENV", "development"),
            ("VITE_APP_ENV", "development"),
            ("DEBUG", True),
            ("EVO_FLOW_ALLOW_INSECURE", True),
            ("POSTGRES_USERNAME", "evoai_dev_password"),
        ):
            with self.subTest(name=name):
                policy = copy.deepcopy(self.commercial_policy)
                policy["settings"][name]["value"] = value
                self.assertTrue(validate_commercial_policy(policy))
        policy = copy.deepcopy(self.commercial_policy)
        policy["settings"]["MEDIA_HOST_ALLOWLIST"] = {"kind": "fixed", "value": "localhost"}
        self.assertTrue(validate_commercial_policy(policy))

    def test_production_settings_use_fixed_policy_and_approved_derivations(self):
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
        self.assertEqual(json.dumps(data, sort_keys=True),
                         json.dumps(self.manifest(), sort_keys=True))
        settings = {item["name"]: item for item in data["variables"]["environment_setting"]}
        self.assertEqual(len(settings), 14)
        for name, expected in (
            ("RAILS_ENV", "production"), ("VITE_APP_ENV", "production"),
            ("DEBUG", False), ("EVO_FLOW_ALLOW_INSECURE", False),
        ):
            self.assertEqual(settings[name]["value"], expected)
            self.assertEqual(settings[name]["source"]["kind"], "commercial_runtime_policy")
        self.assertEqual(settings["MEDIA_HOST_ALLOWLIST"]["value"], "crm-api.cliente-alfa.com.br")
        self.assertEqual(settings["MEDIA_HOST_ALLOWLIST"]["source"]["rule"],
                         "hostname_from_crm_api_v1")
        self.assertEqual(settings["POSTGRES_DATABASE"]["value"], "artgenial_cliente_alfa")
        self.assertEqual(settings["POSTGRES_DATABASE"]["source"]["rule"], "database_from_slug_v1")
        self.assertNotIn("evo_community", json.dumps(data))
        self.assertFalse(any("runtime setting" in item for item in data["delivery"]["pending_requirements"]))
        self.assertTrue(any("runtime secret" in item for item in data["delivery"]["pending_requirements"]))
        self.assertTrue(any("commercial email" in item for item in data["delivery"]["pending_requirements"]))
        self.assertTrue(any("required public and account checks" in item
                            for item in data["delivery"]["pending_requirements"]))
        self.assertFalse(data["delivery"]["ready"])
        self.assertTrue(all(item["reference"].startswith("runtime:")
                            for item in data["variables"]["secret_reference"]))
        self.assertFalse(next(item for item in data["infrastructure"]
                              if item["name"] == "mailhog")["commercial_email_solution"])
        self.assertFalse(next(item for item in data["infrastructure"]
                              if item["name"] == "postgres")["public_endpoint_required"])
        self.assertEqual(next(item for item in data["variables"]["domain_binding"]
                              if item["name"] == "VITE_WS_URL")["value"],
                         self.config["domains"]["crm_api"])
        self.assertEqual(next(item for item in data["validation"]
                              if item["id"] == "crm_websocket")["target"],
                         "wss://crm-api.cliente-alfa.com.br/cable")

    def test_database_rule_is_stable_and_respects_identifier_limit(self):
        self.assertEqual(_commercial_database("cliente-alfa"), "artgenial_cliente_alfa")
        long_slug = "cliente-" + "a" * 80
        result = _commercial_database(long_slug)
        self.assertEqual(result, _commercial_database(long_slug))
        self.assertLessEqual(len(result), 63)
        self.assertNotEqual(result, _commercial_database("cliente-" + "b" * 80))

    def test_nonproduction_settings_remain_pending(self):
        for environment in ("development", "staging"):
            with self.subTest(environment=environment):
                self.config["environment"] = environment
                data = self.manifest()
                settings = data["variables"]["environment_setting"]
                self.assertTrue(all(item["value"] is None and
                                    item["status"] == "explicit_runtime_value_required" for item in settings))
                self.assertTrue(any("runtime setting" in item for item in
                                    data["delivery"]["pending_requirements"]))

    def test_production_manifest_rejects_missing_or_invalid_policy(self):
        self.config["environment"] = "production"
        with self.assertRaises(ConfigurationError):
            build_manifest(self.config, self.catalog, self.checks, self.variables_catalog)
        policy = copy.deepcopy(self.commercial_policy)
        policy["settings"]["DEBUG"]["value"] = True
        with self.assertRaises(ConfigurationError):
            build_manifest(self.config, self.catalog, self.checks, self.variables_catalog, policy)


if __name__ == "__main__":
    unittest.main()
