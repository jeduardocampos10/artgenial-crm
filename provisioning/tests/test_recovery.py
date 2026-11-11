import copy
import unittest
from datetime import datetime, timedelta, timezone

from provisioning.scripts import provision, recovery


class RecoveryGateTest(unittest.TestCase):
    def setUp(self):
        self.policy = provision.load_json(provision.COMMERCIAL_RECOVERY)
        self.installation_key = "eb14dca5-d6ca-40e1-a124-b2f2fa13422a"
        self.now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
        required = sorted(item["id"] for item in self.policy["inventory"] if item["backup_required"])
        self.receipt = {
            "schema_version": 1,
            "installation_key": self.installation_key,
            "backup": {
                "executed_at": "2026-11-11T10:00:00Z",
                "destination": "s3://artgenial-backups/cliente-alfa/backup.tar",
                "encrypted": True,
                "artifact_sha256": "1" * 64,
                "inventory": required,
            },
            "restore": {
                "executed_at": "2026-11-11T11:00:00Z",
                "target_id": "restore-sandbox-20261111",
                "target_environment": "recovery_test",
                "isolated": True,
                "source_sha256": "1" * 64,
                "verified_inventory": required,
                "verification_sha256": "2" * 64,
            },
        }
        self.seal()

    def seal(self):
        self.receipt["evidence_sha256"] = recovery.canonical_hash(
            {key: value for key, value in self.receipt.items() if key != "evidence_sha256"})

    def test_inventory_exactly_covers_every_persistent_compose_volume(self):
        entries = recovery.validate_policy(self.policy)
        self.assertEqual(set(entries), recovery.EXPECTED_VOLUMES)
        self.assertEqual(len(entries), 10)
        required = {name for name, item in entries.items() if item["backup_required"]}
        self.assertEqual(required, {"postgres_data", "redis_data", "rabbitmq_data",
                                    "clickhouse_data", "auth_storage", "crm_storage"})

    def test_valid_external_backup_and_isolated_restore_receipt(self):
        summary = recovery.validate_evidence(self.receipt, self.policy, self.installation_key,
                                             now=self.now)
        self.assertEqual(summary["installation_key"], self.installation_key)
        self.assertEqual(summary["artifact_sha256"], "1" * 64)
        self.assertEqual(summary["evidence_sha256"], self.receipt["evidence_sha256"])

    def test_contract_execution_and_evidence_fail_independently(self):
        bad_policy = copy.deepcopy(self.policy)
        bad_policy["backup_contract"]["destination"] = "local_allowed"
        with self.assertRaisesRegex(recovery.RecoveryError, "backup contract"):
            recovery.validate_policy(bad_policy)

        for mutation, message in (
            (lambda receipt: receipt["backup"].update(destination="file:///tmp/fake"), "external"),
            (lambda receipt: receipt["restore"].update(isolated=False), "isolated"),
            (lambda receipt: receipt["restore"].update(source_sha256="3" * 64), "source hash"),
            (lambda receipt: receipt.update(installation_key="00000000-0000-0000-0000-000000000000"),
             "installation_key"),
        ):
            receipt = copy.deepcopy(self.receipt)
            mutation(receipt)
            receipt["evidence_sha256"] = recovery.canonical_hash(
                {key: value for key, value in receipt.items() if key != "evidence_sha256"})
            with self.subTest(message=message), self.assertRaisesRegex(recovery.RecoveryError, message):
                recovery.validate_evidence(receipt, self.policy, self.installation_key, now=self.now)

        receipt = copy.deepcopy(self.receipt)
        receipt["backup"]["artifact_sha256"] = "4" * 64
        with self.assertRaisesRegex(recovery.RecoveryError, "evidence hash"):
            recovery.validate_evidence(receipt, self.policy, self.installation_key, now=self.now)

    def test_missing_inventory_and_stale_timestamp_are_rejected(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["backup"]["inventory"].pop()
        receipt["restore"]["verified_inventory"] = list(receipt["backup"]["inventory"])
        self.receipt = receipt
        self.seal()
        with self.assertRaisesRegex(recovery.RecoveryError, "cover required"):
            recovery.validate_evidence(self.receipt, self.policy, self.installation_key, now=self.now)

        self.setUp()
        stale_now = self.now + timedelta(seconds=86401)
        with self.assertRaisesRegex(recovery.RecoveryError, "stale"):
            recovery.validate_evidence(self.receipt, self.policy, self.installation_key, now=stale_now)


if __name__ == "__main__":
    unittest.main()
