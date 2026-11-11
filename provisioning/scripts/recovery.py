"""Recovery contracts and validation of externally produced execution evidence.

This module never creates a backup or performs a restore.  It only validates the
versioned contract and a receipt produced after both operations were run.
"""

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit


class RecoveryError(ValueError):
    pass


EXPECTED_VOLUMES = frozenset((
    "postgres_data", "redis_data", "rabbitmq_data", "clickhouse_data",
    "auth_storage", "crm_storage", "crm_cache", "processor_logs",
    "evolution_instances", "caddy_data", "caddy_config",
))
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {
            "policy_version", "inventory", "backup_contract", "restore_contract"}:
        raise RecoveryError("Invalid recovery policy structure")
    if policy["policy_version"] != 1 or type(policy["policy_version"]) is not int:
        raise RecoveryError("Unsupported recovery policy_version")
    inventory = policy["inventory"]
    if not isinstance(inventory, list) or not inventory:
        raise RecoveryError("Recovery inventory must not be empty")
    entries = {}
    fields = {"id", "owner", "path", "classification", "backup_required", "consistent_export"}
    for item in inventory:
        if not isinstance(item, dict) or set(item) != fields:
            raise RecoveryError("Invalid recovery inventory entry")
        if (not all(isinstance(item[name], str) and item[name] for name in
                    ("id", "owner", "path", "classification", "consistent_export"))
                or type(item["backup_required"]) is not bool or not item["path"].startswith("/")):
            raise RecoveryError("Invalid recovery inventory value")
        if item["id"] in entries:
            raise RecoveryError("Duplicate recovery inventory id")
        if item["backup_required"] == (item["consistent_export"] == "none"):
            raise RecoveryError("Required recovery data needs a consistent export method")
        entries[item["id"]] = item
    if set(entries) != EXPECTED_VOLUMES:
        raise RecoveryError("Recovery inventory does not match persistent Compose volumes")
    backup = policy["backup_contract"]
    if backup != {
            "destination": "external_required", "encryption": "required",
            "credentials": "runtime_only", "artifact_hash": "sha256",
            "maximum_evidence_age_seconds": 86400}:
        raise RecoveryError("Unsafe commercial backup contract")
    restore = policy["restore_contract"]
    if restore != {
            "target": "isolated_non_production_required",
            "source_hash_must_match_backup": True,
            "all_required_inventory_must_be_verified": True}:
        raise RecoveryError("Unsafe commercial restore contract")
    return entries


def _timestamp(value, label):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RecoveryError(f"{label} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RecoveryError(f"Invalid {label}") from exc
    if parsed.tzinfo != timezone.utc:
        raise RecoveryError(f"{label} must use UTC")
    return parsed


def validate_evidence(receipt, policy, installation_key, *, now=None, enforce_age=True):
    """Return a secret-free summary only after backup and isolated restore evidence agrees."""
    entries = validate_policy(policy)
    if not isinstance(receipt, dict) or set(receipt) != {
            "schema_version", "installation_key", "backup", "restore", "evidence_sha256"}:
        raise RecoveryError("Invalid recovery evidence structure")
    if receipt["schema_version"] != 1 or type(receipt["schema_version"]) is not int:
        raise RecoveryError("Unsupported recovery evidence schema_version")
    if receipt["installation_key"] != installation_key:
        raise RecoveryError("Recovery evidence installation_key mismatch")
    try:
        expected_hash = canonical_hash({key: receipt[key] for key in receipt if key != "evidence_sha256"})
    except (TypeError, ValueError) as exc:
        raise RecoveryError("Recovery evidence is not canonical JSON") from exc
    if not isinstance(receipt["evidence_sha256"], str) or not hmac.compare_digest(
            receipt["evidence_sha256"], expected_hash):
        raise RecoveryError("Recovery evidence hash mismatch")

    backup = receipt["backup"]
    backup_fields = {"executed_at", "destination", "encrypted", "artifact_sha256", "inventory"}
    if not isinstance(backup, dict) or set(backup) != backup_fields:
        raise RecoveryError("Invalid backup execution evidence")
    try:
        destination = urlsplit(backup["destination"]) if isinstance(backup["destination"], str) else None
    except ValueError as exc:
        raise RecoveryError("Backup destination must be external") from exc
    if (not destination or destination.scheme.lower() in {"", "file", "http"}
            or not destination.netloc or destination.username or destination.password
            or destination.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise RecoveryError("Backup destination must be external")
    if backup["encrypted"] is not True or not SHA256_PATTERN.fullmatch(backup.get("artifact_sha256", "")):
        raise RecoveryError("Backup encryption and SHA-256 evidence are required")

    restore = receipt["restore"]
    restore_fields = {"executed_at", "target_id", "target_environment", "isolated",
                      "source_sha256", "verified_inventory", "verification_sha256"}
    if not isinstance(restore, dict) or set(restore) != restore_fields:
        raise RecoveryError("Invalid restore execution evidence")
    if (restore["isolated"] is not True or restore["target_environment"] != "recovery_test"
            or not isinstance(restore["target_id"], str) or not restore["target_id"].strip()
            or restore["target_id"] == installation_key):
        raise RecoveryError("Restore target must be an identified isolated recovery environment")
    for name in ("source_sha256", "verification_sha256"):
        if not SHA256_PATTERN.fullmatch(restore.get(name, "")):
            raise RecoveryError(f"Invalid restore {name}")
    if not hmac.compare_digest(restore["source_sha256"], backup["artifact_sha256"]):
        raise RecoveryError("Restore source hash does not match the backup artifact")

    required = {name for name, item in entries.items() if item["backup_required"]}
    if (not isinstance(backup["inventory"], list)
            or any(not isinstance(name, str) for name in backup["inventory"])
            or len(backup["inventory"]) != len(set(backup["inventory"]))
            or set(backup["inventory"]) != required):
        raise RecoveryError("Backup evidence does not cover required persistent data")
    if (not isinstance(restore["verified_inventory"], list)
            or any(not isinstance(name, str) for name in restore["verified_inventory"])
            or len(restore["verified_inventory"]) != len(set(restore["verified_inventory"]))
            or set(restore["verified_inventory"]) != required):
        raise RecoveryError("Restore evidence does not verify required persistent data")

    backup_at = _timestamp(backup["executed_at"], "backup.executed_at")
    restore_at = _timestamp(restore["executed_at"], "restore.executed_at")
    if restore_at < backup_at:
        raise RecoveryError("Recovery evidence timestamps are out of order")
    if enforce_age:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise RecoveryError("Current time must be timezone-aware")
        if current < restore_at:
            raise RecoveryError("Recovery evidence timestamps are out of order")
        if (current - restore_at).total_seconds() > policy["backup_contract"]["maximum_evidence_age_seconds"]:
            raise RecoveryError("Recovery evidence is stale")
    return {
        "installation_key": installation_key,
        "backup_executed_at": backup["executed_at"],
        "restore_executed_at": restore["executed_at"],
        "artifact_sha256": backup["artifact_sha256"],
        "evidence_sha256": receipt["evidence_sha256"],
    }
