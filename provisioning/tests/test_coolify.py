import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from provisioning.coolify.validate_images import IMAGE_VARIABLES, validate


PROVISIONING = Path(__file__).resolve().parents[1]
COMPOSE = PROVISIONING / "coolify" / "compose.yaml"


class CoolifyComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = COMPOSE.read_text(encoding="utf-8")

    def service_names(self):
        block = self.text.split("\nservices:\n", 1)[1].split("\nnetworks:\n", 1)[0]
        return {
            match.group(1)
            for match in re.finditer(r"^  ([a-z0-9-]+):\n", block, flags=re.MULTILINE)
        }

    def test_exact_isolated_service_set(self):
        self.assertEqual(
            self.service_names(),
            {
                "postgres", "redis", "rabbitmq", "clickhouse", "evo-auth",
                "evo-auth-sidekiq", "evo-crm", "evo-crm-sidekiq", "evo-core",
                "evo-processor", "evo-bot-runtime", "evolution-api", "evo-flow",
                "evo-frontend", "crm-schema-init", "auth-migration-stamp", "flow-db-init",
            },
        )

    def test_never_publishes_host_ports_or_embeds_ingress(self):
        self.assertNotRegex(self.text, r"(?m)^\s+ports:\s*$")
        self.assertNotRegex(self.text.lower(), r"(?m)^\s+caddy:\s*$")
        self.assertNotRegex(self.text.lower(), r"(?m)^\s+traefik:\s*$")
        self.assertNotRegex(self.text.lower(), r"(?m)^\s+mailhog:\s*$")

    def test_no_global_or_external_namespaces(self):
        self.assertNotRegex(self.text, r"(?m)^name:\s")
        self.assertNotRegex(self.text, r"(?m)^\s+external:\s*true\s*$")
        self.assertNotIn("container_name:", self.text)

    def test_no_runtime_secret_files_or_known_development_defaults(self):
        self.assertNotIn("env_file:", self.text)
        for forbidden in (
            "evoai_dev_password", "evoai_redis_pass", "evoflow-dev-key",
            "CLICKHOUSE_PASSWORD: password", ":-password", ":-postgres",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_required_runtime_values_fail_closed(self):
        required = {
            "INSTALLATION_KEY", "INSTALLATION_NAME", "FRONTEND_HOST", "ADMIN_NAME",
            "ADMIN_EMAIL", "POSTGRES_DATABASE", "POSTGRES_USERNAME", "POSTGRES_PASSWORD",
            "FLOW_DATABASE", "REDIS_PASSWORD", "RABBITMQ_DEFAULT_USER",
            "RABBITMQ_DEFAULT_PASS", "CLICKHOUSE_DATABASE", "CLICKHOUSE_USERNAME",
            "CLICKHOUSE_PASSWORD", "JWT_SECRET_KEY", "SECRET_KEY_BASE", "ENCRYPTION_KEY",
            "DOORKEEPER_JWT_SECRET_KEY", "BOT_RUNTIME_SECRET", "EVOAI_CRM_API_TOKEN",
            "AUTH_APIKEY_INTEGRATION_LOCAL", "EVOLUTION_ADMIN_SECRET",
            "EVOLUTION_WEBHOOK_SECRET", "SMTP_ADDRESS", "SMTP_PORT", "SMTP_USERNAME",
            "SMTP_PASSWORD", "MAILER_SENDER_EMAIL", "FRONTEND_URL", "BACKEND_URL",
            "AUTH_SERVICE_URL", "CORS_ORIGINS", "API_URL", "APP_URL",
            "MEDIA_HOST_ALLOWLIST", "VITE_API_URL", "VITE_AUTH_API_URL", "VITE_WS_URL",
            "VITE_EVOAI_API_URL", "VITE_AGENT_PROCESSOR_URL", "VITE_EVOFLOW_API_URL",
            *IMAGE_VARIABLES,
        }
        for key in required:
            self.assertIn("${" + key + ":?}", self.text, key)

    def test_bootstrap_password_is_optional_only_after_first_bootstrap(self):
        self.assertEqual(self.text.count("${ADMIN_BOOTSTRAP_PASSWORD:-}"), 1)
        self.assertIn("/opt/artgenial/bootstrap_auth.rb", self.text)
        self.assertIn("/opt/artgenial/bootstrap_base.rb", self.text)

    def test_only_six_public_services_are_exposed_to_coolify_proxy(self):
        exposed = set()
        current = None
        in_services = False
        for line in self.text.splitlines():
            if line == "services:":
                in_services = True
                continue
            if line == "networks:":
                break
            if in_services:
                match = re.match(r"^  ([a-z0-9-]+):$", line)
                if match:
                    current = match.group(1)
                elif current and re.match(r"^    expose:", line):
                    exposed.add(current)
        self.assertEqual(exposed, {"evo-frontend", "evo-crm", "evo-auth", "evo-core", "evo-processor", "evo-flow"})

    def test_persistent_inventory_is_explicit_and_private(self):
        volume_block = self.text.split("\nvolumes:\n", 1)[1]
        volumes = {
            match.group(1)
            for match in re.finditer(r"^  ([a-z0-9_]+): \{\}$", volume_block, flags=re.MULTILINE)
        }
        self.assertEqual(
            volumes,
            {
                "postgres_data", "redis_data", "rabbitmq_data", "clickhouse_data",
                "auth_storage", "crm_storage", "crm_cache", "processor_logs",
                "evolution_instances",
            },
        )

    def test_frameworks_run_with_hardened_staging_semantics(self):
        self.assertIn("RAILS_ENV: production", self.text)
        self.assertIn("NODE_ENV: production", self.text)
        self.assertIn("VITE_APP_ENV: staging", self.text)
        self.assertIn('DEBUG: "false"', self.text)
        self.assertIn('EVO_FLOW_ALLOW_INSECURE: "false"', self.text)
        self.assertNotIn("image: clickhouse/clickhouse-server:latest", self.text)
        self.assertIn('TELEMETRY_ENABLED: "false"', self.text)
        self.assertNotRegex(self.text, r"(?m)^\s+TELEMETRY:\s")
        self.assertIn("SERVICE_ROLE: sidekiq", self.text)

    def test_shared_schema_and_flow_database_are_prepared_idempotently(self):
        self.assertIn("crm-schema-init: {condition: service_completed_successfully}", self.text)
        self.assertIn("auth-migration-stamp: {condition: service_completed_successfully}", self.text)
        self.assertIn("flow-db-init: {condition: service_completed_successfully}", self.text)
        self.assertIn("/opt/artgenial/mark_auth_migrations.rb", self.text)
        self.assertIn("/opt/artgenial/prepare-shared-schema.sh", self.text)
        self.assertIn("SELECT 1 FROM pg_database", self.text)
        self.assertEqual(self.text.count('restart: "no"'), 3)
        self.assertEqual(self.text.count("exclude_from_hc: true"), 3)
        stamp = (PROVISIONING / "commercial" / "mark_auth_migrations.rb").read_text(encoding="utf-8")
        self.assertIn("Auth migration stamp skipped for existing installation", stamp)
        self.assertIn("if User.exists?", stamp)
        self.assertIn("ActiveRecord::SchemaMigration.new(connection)", stamp)
        self.assertNotIn("connection.schema_migration", stamp)

    def test_all_auth_migration_entrypoints_use_rails_71_schema_migration_api(self):
        repository_root = PROVISIONING.parent
        sources = {
            "migration stamp": (PROVISIONING / "commercial" / "mark_auth_migrations.rb").read_text(encoding="utf-8"),
            "Makefile": (repository_root / "Makefile").read_text(encoding="utf-8"),
            "setup.sh": (repository_root / "setup.sh").read_text(encoding="utf-8"),
        }
        for name, source in sources.items():
            with self.subTest(source=name):
                self.assertIn("ActiveRecord::SchemaMigration.new(", source)
                self.assertNotIn("connection.schema_migration", source)

    def test_all_relative_bind_mount_sources_exist(self):
        expected = {
            "provisioning/coolify/prepare-shared-schema.sh",
            "provisioning/commercial/mark_auth_migrations.rb",
            "provisioning/commercial/bootstrap_auth.rb",
            "provisioning/commercial/bootstrap_base.rb",
            "provisioning/commercial/processor-entrypoint.sh",
            "provisioning/commercial/bot-entrypoint.sh",
            "provisioning/commercial/flow-entrypoint.sh",
        }
        repository_root = PROVISIONING.parent
        for relative in expected:
            self.assertTrue((repository_root / relative).is_file(), relative)

    def test_final_coolify_topology_never_builds_on_the_server(self):
        self.assertNotRegex(self.text, r"(?m)^\s+build:\s*(?:$|\{)")
        self.assertNotIn("context:", self.text)

    def test_compose_has_no_repository_file_bind_mounts(self):
        volume_lines = re.findall(r"(?m)^\s+-?\s*[^#\n]*:/[^#\n]*$", self.text)
        self.assertFalse(
            [line for line in volume_lines if "./" in line or "/provisioning/" in line],
            "repository files must be embedded in immutable images",
        )
        self.assertNotIn("./provisioning/", self.text)

    def test_required_embedded_asset_paths_are_used(self):
        for path in (
            "/opt/artgenial/prepare-shared-schema.sh",
            "/opt/artgenial/mark_auth_migrations.rb",
            "/opt/artgenial/bootstrap_auth.rb",
            "/opt/artgenial/bootstrap_base.rb",
            "/opt/artgenial/processor-entrypoint.sh",
            "/opt/artgenial/bot-entrypoint.sh",
            "/opt/artgenial/flow-entrypoint.sh",
        ):
            self.assertIn(path, self.text)

    def test_root_image_contexts_embed_required_assets(self):
        preparer = PROVISIONING / "coolify" / "prepare-hml-image-context.sh"
        expected = {
            "auth": ("mark_auth_migrations.rb", "bootstrap_auth.rb"),
            "bot-runtime": ("bot-entrypoint.sh",),
            "flow": ("flow-entrypoint.sh",),
            "evolution-api": (),
        }
        with tempfile.TemporaryDirectory() as temporary:
            for component, assets in expected.items():
                context = Path(temporary) / component
                context.mkdir()
                (context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
                subprocess.run(
                    ["sh", str(preparer), component, str(context)],
                    check=True,
                    cwd=PROVISIONING.parent,
                )
                dockerfile = (context / "Dockerfile.hml").read_text(encoding="utf-8")
                for asset in assets:
                    embedded = context / ".artgenial" / asset
                    source = PROVISIONING / "commercial" / asset
                    self.assertEqual(embedded.read_bytes(), source.read_bytes())
                    self.assertIn(asset, dockerfile)
                if not assets:
                    self.assertFalse((context / ".artgenial").exists())

    def test_web_workers_and_one_shots_reuse_the_same_images(self):
        self.assertEqual(self.text.count("image: ${CRM_IMAGE:?}"), 3)
        self.assertEqual(self.text.count("image: ${AUTH_IMAGE:?}"), 3)
        for variable in set(IMAGE_VARIABLES) - {"CRM_IMAGE", "AUTH_IMAGE"}:
            self.assertEqual(self.text.count(f"image: ${{{variable}:?}}"), 1, variable)

    def test_cpu_limits_never_exceed_one_core(self):
        limits = [float(value) for value in re.findall(r"(?m)^\s+cpus:\s*([0-9.]+)$", self.text)]
        self.assertTrue(limits)
        self.assertLessEqual(max(limits), 1.0)
        self.assertIn(0.25, limits)
        self.assertIn(0.5, limits)

    def test_image_validator_accepts_only_digest_or_full_commit(self):
        digest = "a" * 64
        commit = "b" * 40
        valid = {
            variable: f"ghcr.io/jeduardocampos10/artgenial-hml-{variable.lower().replace('_image', '').replace('_', '-')}:{commit}"
            for variable in IMAGE_VARIABLES
        }
        self.assertEqual(validate(valid), [])
        valid["CRM_IMAGE"] = f"ghcr.io/jeduardocampos10/artgenial-hml-crm@sha256:{digest}"
        self.assertEqual(validate(valid), [])
        valid["CRM_IMAGE"] = "ghcr.io/jeduardocampos10/artgenial-hml-crm:develop"
        self.assertEqual(len(validate(valid)), 1)

    def test_data_services_remain_private(self):
        for service in ("postgres", "redis", "rabbitmq", "clickhouse"):
            block = self.text.split(f"  {service}:\n", 1)[1].split("\n  ", 1)[0]
            self.assertNotIn("ports:", block, service)
            self.assertNotIn("expose:", block, service)
        self.assertIn("networks: [private]", self.text)


if __name__ == "__main__":
    unittest.main()
