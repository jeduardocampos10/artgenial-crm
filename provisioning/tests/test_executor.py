import copy
import hashlib
import json
import unittest

from provisioning.scripts.executor import (
    ExecutorError, PHASES, attest_commercial_email, attest_initialization,
    attest_secret, attest_service, attest_setting, block_phase,
    complete_delivery, complete_phase, create_state, delivery_blockers,
    fail_phase, manifest_fingerprint, record_check, resume_state, retry_phase,
    start_phase, validate_manifest, validate_state,
)
from provisioning.scripts.provision import (
    CATALOG, CHECKS, COMMERCIAL_RUNTIME, DEPLOYMENT_VARIABLES, EXAMPLE,
    build_manifest, load_json,
)


class ExecutorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_json(CATALOG)
        cls.checks = load_json(CHECKS)
        cls.variables_catalog = load_json(DEPLOYMENT_VARIABLES)

    def manifest(self, environment="development"):
        config = load_json(EXAMPLE)
        config["environment"] = environment
        if environment == "production":
            config["installation_name"] = "Cliente Alfa"
            config["slug"] = "cliente-alfa"
            config["installation_key"] = "eb14dca5-d6ca-40e1-a124-b2f2fa13422a"
            config["domains"] = {key: f"https://{key.replace('_', '-')}.cliente-alfa.com.br"
                                 for key in config["domains"]}
        policy = load_json(COMMERCIAL_RUNTIME) if environment == "production" else None
        return build_manifest(config, self.catalog, self.checks, self.variables_catalog, policy)

    def progress(self, manifest, stop_before=None, failed_check=None, omitted_secret=None,
                 omitted_setting=None, omit_email=False):
        state = create_state(manifest)
        for phase in PHASES[:-1]:
            if phase == stop_before:
                return state
            state = start_phase(state, manifest, phase)
            if phase == "PREPARACAO":
                for name in state["evidence"]["secrets"]:
                    if name != omitted_secret:
                        state = attest_secret(state, manifest, name)
                for name in state["evidence"]["settings"]:
                    if name != omitted_setting:
                        state = attest_setting(state, manifest, name)
                if omitted_secret is not None or omitted_setting is not None:
                    return state
            elif phase == "INFRAESTRUTURA":
                for name in state["evidence"]["services"]:
                    state = attest_service(state, manifest, name)
                if manifest["installation"]["environment"] == "production" and not omit_email:
                    state = attest_commercial_email(state, manifest)
            elif phase == "INICIALIZACAO":
                for name in state["evidence"]["initialization"]:
                    state = attest_initialization(state, manifest, name)
            else:
                for name in state["evidence"]["checks"]:
                    state = record_check(state, manifest, name, name != failed_check)
            state = complete_phase(state, manifest, phase)
        return state

    def test_state_and_fingerprint_are_deterministic_and_manifest_change_rejected(self):
        manifest = self.manifest()
        first = create_state(manifest)
        self.assertEqual(first, create_state(manifest))
        self.assertEqual(len(first["manifest_fingerprint"]["value"]), 64)
        self.assertEqual(first["manifest_fingerprint"]["value"], manifest_fingerprint(manifest))
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(manifest_fingerprint(manifest), hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        self.assertEqual(resume_state(first, manifest), first)
        altered = copy.deepcopy(manifest)
        altered["installation"]["installation_name"] += " Nova"
        self.assertNotEqual(manifest_fingerprint(manifest), manifest_fingerprint(altered))
        with self.assertRaisesRegex(ExecutorError, "fingerprint"):
            resume_state(first, altered)
        self.assertEqual(first["manifest_fingerprint"]["value"], manifest_fingerprint(manifest))

    def test_identity_and_state_tampering_are_rejected(self):
        manifest = self.manifest()
        state = create_state(manifest)
        for field, value in (("installation_key", "eb14dca5-d6ca-40e1-a124-b2f2fa13422a"),
                             ("slug", "other"), ("environment", "staging")):
            changed = copy.deepcopy(manifest)
            changed["installation"][field] = value
            with self.subTest(field=field), self.assertRaises(ExecutorError):
                resume_state(state, changed)
        for field, value in (("state_version", 2), ("phases", {**state["phases"], "PREPARACAO": "arbitrary"}),
                             ("delivery", {"ready": True})):
            changed = copy.deepcopy(state)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ExecutorError):
                validate_state(changed, manifest)
        changed = copy.deepcopy(state)
        changed["evidence"]["secrets"]["POSTGRES_PASSWORD"] = "fake-secret-for-test"
        with self.assertRaises(ExecutorError):
            validate_state(changed, manifest)
        changed = copy.deepcopy(state)
        changed["manifest_fingerprint"]["value"] = "0" * 64
        with self.assertRaisesRegex(ExecutorError, "fingerprint"):
            validate_state(changed, manifest)
        changed = copy.deepcopy(state)
        changed["evidence"]["secrets"]["POSTGRES_PASSWORD"] = True
        with self.assertRaisesRegex(ExecutorError, "audit"):
            validate_state(changed, manifest)
        changed = copy.deepcopy(state)
        changed["audit"].append({"sequence": 1, "action": "attest", "phase": "PREPARACAO",
                                 "subject": "POSTGRES_PASSWORD", "result": "true"})
        with self.assertRaises(ExecutorError):
            validate_state(changed, manifest)

    def test_phase_order_retry_and_idempotence(self):
        manifest = self.manifest()
        state = create_state(manifest)
        self.assertEqual(list(state["phases"]), list(PHASES))
        self.assertTrue(all(value == "pending" for value in state["phases"].values()))
        with self.assertRaises(ExecutorError):
            start_phase(state, manifest, "INICIALIZACAO")
        with self.assertRaises(ExecutorError):
            complete_phase(state, manifest, "ENTREGA")
        state = start_phase(state, manifest, "PREPARACAO")
        self.assertEqual(state, start_phase(state, manifest, "PREPARACAO"))
        self.assertEqual(len(state["audit"]), 1)
        state = fail_phase(state, manifest, "PREPARACAO")
        with self.assertRaises(ExecutorError):
            start_phase(state, manifest, "PREPARACAO")
        state = retry_phase(state, manifest, "PREPARACAO")
        state = start_phase(state, manifest, "PREPARACAO")
        state = block_phase(state, manifest, "PREPARACAO")
        self.assertEqual(state["phases"]["PREPARACAO"], "blocked")
        state = retry_phase(state, manifest, "PREPARACAO")
        state = start_phase(state, manifest, "PREPARACAO")
        for name in state["evidence"]["secrets"]:
            state = attest_secret(state, manifest, name)
        for name in state["evidence"]["settings"]:
            state = attest_setting(state, manifest, name)
        state = complete_phase(state, manifest, "PREPARACAO")
        self.assertEqual(state, complete_phase(state, manifest, "PREPARACAO"))
        self.assertEqual([event["sequence"] for event in state["audit"]], list(range(1, len(state["audit"]) + 1)))

    def test_unknown_evidence_and_secret_value_are_rejected(self):
        manifest = self.manifest()
        state = start_phase(create_state(manifest), manifest, "PREPARACAO")
        with self.assertRaises(ExecutorError):
            attest_secret(state, manifest, "UNKNOWN_SECRET")
        with self.assertRaises(TypeError):
            attest_secret(state, manifest, "POSTGRES_PASSWORD", "fake-secret-for-test")
        state = attest_secret(state, manifest, "POSTGRES_PASSWORD")
        self.assertEqual(state, attest_secret(state, manifest, "POSTGRES_PASSWORD"))
        serialized = json.dumps(state)
        self.assertNotIn("fake-secret-for-test", serialized)
        self.assertNotIn("runtime:POSTGRES_PASSWORD", serialized)
        self.assertNotIn("password", state["installation"])
        with self.assertRaises(ExecutorError):
            attest_setting(state, manifest, "UNKNOWN_SETTING")
        for name in state["evidence"]["secrets"]:
            state = attest_secret(state, manifest, name)
        for name in state["evidence"]["settings"]:
            state = attest_setting(state, manifest, name)
        state = complete_phase(state, manifest, "PREPARACAO")
        state = start_phase(state, manifest, "INFRAESTRUTURA")
        with self.assertRaises(ExecutorError):
            attest_service(state, manifest, "unknown-service")
        with self.assertRaises(ExecutorError):
            complete_phase(state, manifest, "INFRAESTRUTURA")
        for name in state["evidence"]["services"]:
            state = attest_service(state, manifest, name)
        state = complete_phase(state, manifest, "INFRAESTRUTURA")
        state = start_phase(state, manifest, "INICIALIZACAO")
        with self.assertRaises(ExecutorError):
            attest_initialization(state, manifest, "unknown-step")
        for name in state["evidence"]["initialization"]:
            state = attest_initialization(state, manifest, name)
        state = complete_phase(state, manifest, "INICIALIZACAO")
        state = start_phase(state, manifest, "VALIDACAO")
        with self.assertRaises(ExecutorError):
            record_check(state, manifest, "unknown-check", True)
        with self.assertRaises(ExecutorError):
            record_check(state, manifest, "frontend_public", "true")

    def test_all_delivery_gates_and_fourteen_checks(self):
        manifest = self.manifest()
        self.assertEqual(len(manifest["delivery"]["required_check_ids"]), 14)
        for phase in PHASES[:-1]:
            state = self.progress(manifest, stop_before=phase)
            with self.subTest(phase=phase), self.assertRaises(ExecutorError):
                complete_delivery(state, manifest)
        state = self.progress(manifest, failed_check="crm_websocket")
        self.assertIn("check:crm_websocket", delivery_blockers(state, manifest))
        with self.assertRaises(ExecutorError):
            complete_delivery(state, manifest)
        state = self.progress(manifest)
        self.assertEqual(delivery_blockers(state, manifest), [])
        delivered = complete_delivery(state, manifest)
        self.assertTrue(delivered["delivery"]["ready"])
        self.assertEqual(delivered["phases"]["ENTREGA"], "completed")
        self.assertEqual(delivered, complete_delivery(delivered, manifest))
        self.assertFalse(state["delivery"]["ready"])

    def test_unresolved_secret_and_setting_block_delivery(self):
        manifest = self.manifest()
        initial = create_state(manifest)
        self.assertIn("RAILS_ENV", initial["evidence"]["settings"])
        secret_state = self.progress(manifest, omitted_secret="POSTGRES_PASSWORD")
        self.assertEqual(secret_state["phases"]["PREPARACAO"], "in_progress")
        self.assertIn("secret:POSTGRES_PASSWORD", delivery_blockers(secret_state, manifest))
        with self.assertRaisesRegex(ExecutorError, "Preparation secrets or runtime settings"):
            complete_phase(secret_state, manifest, "PREPARACAO")
        setting_state = self.progress(manifest, omitted_setting="RAILS_ENV")
        self.assertEqual(setting_state["phases"]["PREPARACAO"], "in_progress")
        self.assertIn("setting:RAILS_ENV", delivery_blockers(setting_state, manifest))
        with self.assertRaisesRegex(ExecutorError, "Preparation secrets or runtime settings"):
            complete_phase(setting_state, manifest, "PREPARACAO")

    def test_preparation_requires_all_secret_and_setting_evidence(self):
        manifest = self.manifest()
        state = start_phase(create_state(manifest), manifest, "PREPARACAO")
        with self.assertRaisesRegex(ExecutorError, "Preparation secrets or runtime settings"):
            complete_phase(state, manifest, "PREPARACAO")
        missing_secret = next(iter(state["evidence"]["secrets"]))
        for name in state["evidence"]["secrets"]:
            if name != missing_secret:
                state = attest_secret(state, manifest, name)
        with self.assertRaises(ExecutorError):
            complete_phase(state, manifest, "PREPARACAO")
        state = attest_secret(state, manifest, missing_secret)
        settings = list(state["evidence"]["settings"])
        self.assertTrue(settings)
        for name in settings[:-1]:
            state = attest_setting(state, manifest, name)
        with self.assertRaises(ExecutorError):
            complete_phase(state, manifest, "PREPARACAO")
        state = attest_setting(state, manifest, settings[-1])
        state = complete_phase(state, manifest, "PREPARACAO")
        self.assertEqual(state["phases"]["PREPARACAO"], "completed")

    def test_audited_preparation_without_required_evidence_is_rejected(self):
        manifest = self.manifest()
        state = start_phase(create_state(manifest), manifest, "PREPARACAO")
        for name in state["evidence"]["secrets"]:
            if name != "POSTGRES_PASSWORD":
                state = attest_secret(state, manifest, name)
        for name in state["evidence"]["settings"]:
            state = attest_setting(state, manifest, name)
        tampered = copy.deepcopy(state)
        tampered["phases"]["PREPARACAO"] = "completed"
        tampered["audit"].append({"sequence": len(tampered["audit"]) + 1,
                                  "action": "complete", "phase": "PREPARACAO",
                                  "subject": "PREPARACAO", "result": "completed"})
        with self.assertRaisesRegex(ExecutorError, "Audited preparation requirements incomplete"):
            validate_state(tampered, manifest)

    def test_production_requires_commercial_email_but_nonproduction_does_not(self):
        production = self.manifest("production")
        state = self.progress(production, omit_email=True)
        self.assertEqual(delivery_blockers(state, production), ["commercial_email"])
        self.assertIn("commercial_email", delivery_blockers(state, production))
        with self.assertRaises(ExecutorError):
            complete_delivery(state, production)
        self.assertTrue(complete_delivery(self.progress(production), production)["delivery"]["ready"])
        for environment in ("development", "staging"):
            manifest = self.manifest(environment)
            state = self.progress(manifest)
            self.assertTrue(complete_delivery(state, manifest)["delivery"]["ready"])

    def test_manifest_boundary_rejects_unsafe_shape(self):
        manifest = self.manifest()
        mutations = []
        bad = copy.deepcopy(manifest)
        bad["manifest_version"] = 2
        mutations.append(bad)
        bad = copy.deepcopy(manifest)
        bad["infrastructure"][0]["host_port"] = 5432
        mutations.append(bad)
        bad = copy.deepcopy(manifest)
        bad["infrastructure"][0]["public_endpoint_required"] = True
        mutations.append(bad)
        bad = copy.deepcopy(manifest)
        bad["variables"]["secret_reference"][0]["value"] = "fake-secret-for-test"
        mutations.append(bad)
        bad = copy.deepcopy(manifest)
        bad["delivery"]["required_check_ids"] = []
        mutations.append(bad)
        bad = copy.deepcopy(manifest)
        bad["delivery"]["pending_requirements"].append("Unknown mandatory requirement")
        mutations.append(bad)
        for index, bad in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ExecutorError):
                validate_manifest(bad)

    def test_executor_slug_starts_with_letter_like_contract(self):
        manifest = self.manifest()
        manifest["installation"]["slug"] = "1-cliente"
        with self.assertRaisesRegex(ExecutorError, "Invalid slug"):
            validate_manifest(manifest)

    def test_commercial_email_reattest_after_infrastructure_completion(self):
        manifest = self.manifest("production")
        state = self.progress(manifest, stop_before="INICIALIZACAO")
        self.assertEqual(state["phases"]["INFRAESTRUTURA"], "completed")
        self.assertEqual(attest_commercial_email(state, manifest), state)


if __name__ == "__main__":
    unittest.main()
