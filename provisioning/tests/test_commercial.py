import copy
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provisioning.commercial import install
from provisioning.scripts import executor, provision


class CommercialInstallerTest(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(provision.load_json(provision.EXAMPLE))
        self.config.update(environment="production", installation_name="Cliente Alfa",
                           slug="cliente-alfa", installation_key="eb14dca5-d6ca-40e1-a124-b2f2fa13422a")
        self.config["domains"] = {key: f"https://{key.replace('_', '-')}.cliente-alfa.com.br"
                                  for key in self.config["domains"]}
        self.config["administrator"]["email"] = "admin@cliente-alfa.com.br"
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "installation.json"
        self.runtime_path = self.root / "runtime.env"
        self.state_path = self.root / "executor.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.runtime = {key: "synthetic_" + key.lower() + "_abcdefghijklmnopqrstuvwxyz"
                        for key in install.RUNTIME_KEYS}
        self.runtime.update(SMTP_ADDRESS="smtp.cliente-alfa.com.br", SMTP_PORT="587",
                            MAILER_SENDER_EMAIL="no-reply@cliente-alfa.com.br")
        self.write_runtime()

    def write_runtime(self):
        self.runtime_path.write_text("\n".join(f"{key}={value}" for key, value in self.runtime.items()), encoding="utf-8")
        os.chmod(self.runtime_path, 0o600)

    def test_manifest_and_executor_state_never_contain_runtime_credentials(self):
        manifest, state, env, runtime = install.prepare(self.config_path, self.runtime_path, self.state_path)
        self.assertEqual(manifest["variables"]["environment_setting"][-1]["status"], "resolved_by_commercial_policy")
        self.assertEqual(env["VITE_WS_URL"], self.config["domains"]["crm_api"])
        self.assertEqual(env["POSTGRES_DATABASE"], "artgenial_cliente_alfa")
        self.assertNotEqual(env["FLOW_DATABASE"], env["POSTGRES_DATABASE"])
        self.assertLessEqual(len(env["FLOW_DATABASE"]), 63)
        self.assertEqual(runtime, self.runtime)
        self.assertFalse(set(runtime) & set(env))
        for entry in manifest["variables"]["secret_reference"]:
            self.assertEqual(entry["reference"], "runtime:" + entry["name"])
        install.save_state(self.state_path, state)
        serialized = json.dumps(manifest) + self.state_path.read_text(encoding="utf-8")
        for value in self.runtime.values():
            self.assertNotIn(value, serialized)
            self.assertNotIn(value, json.dumps(env))
        self.assertEqual(executor.resume_state(json.loads(self.state_path.read_text(encoding="utf-8")), manifest), state)

    def test_runtime_rejects_insecure_mail_and_admin_password(self):
        for key, value in (("SMTP_ADDRESS", "localhost"), ("SMTP_ADDRESS", "mailhog"),
                           ("POSTGRES_PASSWORD", "has@delimiter"), ("SMTP_PORT", "99999")):
            with self.subTest(key=key, value=value):
                original = self.runtime[key]
                self.runtime[key] = value
                self.write_runtime()
                with self.assertRaises(install.InstallError):
                    install.prepare(self.config_path, self.runtime_path, self.state_path)
                self.runtime[key] = original
        self.runtime["ADMIN_PASSWORD"] = "synthetic_only"
        self.write_runtime()
        with self.assertRaises(install.InstallError):
            install.prepare(self.config_path, self.runtime_path, self.state_path)

    def test_compose_security_contract(self):
        source = install.COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("mailhog:", source)
        self.assertNotIn("artgenial.com.br", source)
        self.assertNotIn("evo_community", source)
        for port in ("55434", "56381", "55672", "18123", "19000", "3010", "5173"):
            self.assertNotIn(port, source)
        self.assertNotIn("development", source)
        self.assertNotIn("DEBUG: true", source)
        self.assertNotIn("EVO_FLOW_ALLOW_INSECURE: true", source)
        self.assertIn("RAILS_ENV: production", source)
        self.assertIn("VITE_APP_ENV: production", source)
        self.assertIn("DEBUG: \"false\"", source)
        self.assertIn("EVO_FLOW_ALLOW_INSECURE: \"false\"", source)
        self.assertIn("VITE_WS_URL: ${VITE_WS_URL:?}", source)
        self.assertNotIn("wss://${VITE_WS_URL", source)
        self.assertIn("networks: [private]", source)
        common = source.split("x-common: &common\n", 1)[1].split("x-rails: &rails", 1)[0]
        self.assertNotIn("env_file", common)
        self.assertNotIn("ARTGENIAL_RUNTIME_ENV_FILE", source)
        self.assertEqual(source.count('ports: ["80:80", "443:443"]'), 1)
        for service in ("postgres", "redis", "rabbitmq", "clickhouse"):
            block = re.split(r"\n  [a-z][a-z0-9-]*:\n", source.split(f"  {service}:\n", 1)[1], maxsplit=1)[0]
            self.assertNotIn("ports:", block)
            self.assertIn("volumes:", block)
        for value in self.runtime.values():
            self.assertNotIn(value, source)
        blocks = dict((match.group(1), match.group(2)) for match in re.finditer(
            r"(?ms)^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|^networks:\n)",
            source.split("services:\n", 1)[1]))
        self.assertEqual(set(blocks), {item["name"] for item in provision.load_json(provision.CATALOG)["services"]}
                         - {"mailhog"} | {"ingress"})
        for service, block in blocks.items():
            if service in {"evo-frontend", "ingress"}:
                self.assertNotIn("env_file", block)
            else:
                self.assertIn(f"env_file: [${{ARTGENIAL_SERVICE_ENV_DIR:?}}/{service}.env]", block)
        self.assertNotRegex(source, r"(?im)^\s*(?:POSTGRES_PASSWORD|REDIS_PASSWORD|SMTP_PASSWORD|JWT_SECRET_KEY|SECRET_KEY_BASE):\s*[^$\s]")
        self.assertNotRegex(source, r"(?im)^\s*[A-Z_]*(?:PASSWORD|SECRET|TOKEN):\s*['\"]?[A-Za-z0-9]")

    def test_checks_come_from_official_catalog(self):
        manifest, _, _, _ = install.prepare(self.config_path, self.runtime_path, self.state_path)
        checks = provision.load_json(provision.CHECKS)["checks"]
        self.assertEqual([item["id"] for item in manifest["validation"]], [item["id"] for item in checks])
        self.assertEqual(next(item for item in manifest["validation"] if item["id"] == "crm_websocket")["target"],
                         "wss://crm-api.cliente-alfa.com.br/cable")

    def test_smtp_attestation_only_after_successful_handshake(self):
        manifest, state, _, _ = install.prepare(self.config_path, self.runtime_path, self.state_path)
        with patch("provisioning.commercial.install.smtplib.SMTP", side_effect=OSError("synthetic failure")):
            with self.assertRaises(install.InstallError):
                install.verify_smtp(self.runtime)
        self.assertFalse(state["evidence"]["commercial_email"])

    def test_shared_schema_is_loaded_only_for_empty_database(self):
        _, _, env, _ = install.prepare(self.config_path, self.runtime_path, self.state_path)
        commands = []

        def fake_compose(_env, *args):
            commands.append(args)
            if "SELECT count(*)" in " ".join(args):
                return "0"
            return ""

        with patch("provisioning.commercial.install.compose", side_effect=fake_compose):
            install.prepare_shared_schema(env)
        self.assertTrue(any("db:schema:load" in command for command in commands))
        self.assertTrue(any("mark_auth_migrations.rb" in " ".join(command) for command in commands))
        commands.clear()

        def existing_compose(_env, *args):
            commands.append(args)
            joined = " ".join(args)
            if "SELECT count(*)" in joined:
                return "42"
            if "to_regclass" in joined:
                return "t"
            if "SELECT 1 FROM pg_database" in joined:
                return "1"
            return ""

        with patch("provisioning.commercial.install.compose", side_effect=existing_compose):
            install.prepare_shared_schema(env)
        self.assertFalse(any("db:schema:load" in command for command in commands))

    def test_credentials_are_granted_only_to_consuming_services(self):
        manifest, _, env, runtime = install.prepare(self.config_path, self.runtime_path, self.state_path)
        grants = install.service_runtime_values(manifest, runtime)
        self.assertNotIn("evo-frontend", grants)
        self.assertNotIn("ingress", grants)
        expected = {
            "POSTGRES_PASSWORD": {"postgres", "evo-auth", "evo-auth-sidekiq", "evo-crm",
                                  "evo-crm-sidekiq", "evo-processor", "evo-flow"},
            "REDIS_PASSWORD": {"redis", "evo-auth", "evo-auth-sidekiq", "evo-crm",
                               "evo-crm-sidekiq", "evo-processor", "evo-bot-runtime", "evo-flow"},
            "JWT_SECRET_KEY": {"evo-auth", "evo-auth-sidekiq", "evo-crm", "evo-crm-sidekiq",
                               "evo-core", "evo-processor"},
            "SECRET_KEY_BASE": {"evo-auth", "evo-auth-sidekiq", "evo-crm", "evo-crm-sidekiq"},
            "ENCRYPTION_KEY": {"evo-crm", "evo-crm-sidekiq", "evo-core", "evo-processor"},
            "DOORKEEPER_JWT_SECRET_KEY": {"evo-auth", "evo-auth-sidekiq"},
            "BOT_RUNTIME_SECRET": {"evo-crm", "evo-crm-sidekiq", "evo-bot-runtime"},
            "EVOAI_CRM_API_TOKEN": {"evo-auth", "evo-crm", "evo-crm-sidekiq", "evo-flow"},
            "AUTH_APIKEY_INTEGRATION_LOCAL": {"evo-crm", "evo-crm-sidekiq", "evo-flow"},
            "SMTP_PASSWORD": install.SMTP_SERVICES,
            "RABBITMQ_DEFAULT_PASS": {"rabbitmq", "evo-flow"},
            "CLICKHOUSE_PASSWORD": {"clickhouse", "evo-flow"},
        }
        for key, services in expected.items():
            with self.subTest(key=key):
                self.assertEqual({name for name, values in grants.items() if key in values}, services)
        self.assertEqual(grants["evo-core"]["DB_PASSWORD"], runtime["POSTGRES_PASSWORD"])
        self.assertNotIn("POSTGRES_PASSWORD", grants["evo-core"])
        self.assertEqual(grants["evo-flow"]["EVO_AUTH_API_TOKEN"], runtime["EVOAI_CRM_API_TOKEN"])
        self.assertEqual(grants["evo-crm"]["EVO_AI_ENCRYPTION_KEY"], runtime["ENCRYPTION_KEY"])
        self.assertTrue(all("SMTP_PASSWORD" not in values for name, values in grants.items()
                            if name not in install.SMTP_SERVICES))
        self.assertFalse(set(runtime) & set(env))

    def test_service_files_are_outside_git_and_not_passed_in_process_env(self):
        manifest, _, env, runtime = install.prepare(self.config_path, self.runtime_path, self.state_path)
        with patch.object(install, "ROOT", self.root):
            with self.assertRaises(install.InstallError):
                install.read_runtime(self.runtime_path)
            with self.assertRaises(install.InstallError):
                install.write_service_env_files(self.root / "scoped", manifest, runtime)
        directory = self.root / "scoped"
        install.write_service_env_files(directory, manifest, runtime)
        self.assertFalse((directory / "evo-frontend.env").exists())
        self.assertFalse((directory / "ingress.env").exists())
        for service, values in install.service_runtime_values(manifest, runtime).items():
            path = directory / f"{service}.env"
            content = path.read_text(encoding="utf-8")
            self.assertEqual(dict(line.split("=", 1) for line in content.splitlines()), values)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o077, 0)
        from types import SimpleNamespace
        with patch("provisioning.commercial.install.subprocess.run",
                   return_value=SimpleNamespace(returncode=0, stdout="")) as run:
            install.compose(env, "config", "--quiet")
        process_env = run.call_args.kwargs["env"]
        for value in runtime.values():
            self.assertNotIn(value, process_env.values())


if __name__ == "__main__":
    unittest.main()
