"""Pure, local execution state for a validated ArtGenial deployment manifest.

This module records attestations only. It never performs the attested work.
"""

import copy
import hashlib
import json
import re
import uuid


PHASES = ("PREPARACAO", "INFRAESTRUTURA", "INICIALIZACAO", "VALIDACAO", "ENTREGA")
STATUSES = frozenset(("pending", "in_progress", "completed", "blocked", "failed"))
PUBLIC_KEYS = frozenset(("frontend", "crm_api", "auth_api", "core_api", "processor_api", "flow_api"))
PRIVATE_SERVICES = frozenset(("postgres", "redis", "rabbitmq", "clickhouse", "evo-bot-runtime", "mailhog"))
EMAIL_PENDING = "Select a commercial email solution; MailHog is for local testing only"
CHECKS_PENDING = "Execute and pass all required public and account checks"


class ExecutorError(ValueError):
    """The manifest, state, or requested transition is unsafe."""


def _require(condition, message):
    if not condition:
        raise ExecutorError(message)


def _keys(value, expected, label):
    _require(type(value) is dict and set(value) == set(expected), f"Invalid {label} structure")


def _entries(items, key, label):
    _require(type(items) is list and bool(items), f"Invalid {label} list")
    result = {}
    for item in items:
        _require(type(item) is dict and type(item.get(key)) is str and item[key], f"Invalid {label} entry")
        _require(item[key] not in result, f"Duplicate {label}: {item[key]}")
        result[item[key]] = item
    return result


def manifest_fingerprint(manifest):
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(manifest):
    _keys(manifest, ("manifest_version", "installation", "infrastructure", "public_endpoints",
                     "variables", "initialization", "validation", "delivery"), "manifest")
    _require(type(manifest["manifest_version"]) is int and manifest["manifest_version"] == 1,
             "Unsupported manifest_version")
    identity = manifest["installation"]
    _keys(identity, ("installation_name", "installation_key", "slug", "environment"), "installation")
    key = identity["installation_key"]
    try:
        _require(type(key) is str and str(uuid.UUID(key)) == key, "Invalid installation_key")
    except (ValueError, AttributeError, TypeError) as exc:
        raise ExecutorError("Invalid installation_key") from exc
    _require(type(identity["slug"]) is str and
             re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identity["slug"]) is not None, "Invalid slug")
    _require(identity["environment"] in ("development", "staging", "production"), "Invalid environment")
    _require(type(identity["installation_name"]) is str and bool(identity["installation_name"].strip()),
             "Invalid installation_name")
    _keys(manifest["public_endpoints"], PUBLIC_KEYS, "public_endpoints")
    for domain in manifest["public_endpoints"].values():
        _require(type(domain) is str and domain.startswith(("https://", "http://")), "Invalid public endpoint")
    services = _entries(manifest["infrastructure"], "name", "service")
    _require(len(services) >= len(PRIVATE_SERVICES) and PRIVATE_SERVICES <= services.keys(),
             "Required private service missing")
    for name, service in services.items():
        _require(type(service.get("public_endpoint_required")) is bool, f"Invalid service visibility: {name}")
        _require(not any(port in service for port in ("host_port", "host_ports", "ports")),
                 f"Host port forbidden: {name}")
        if name in PRIVATE_SERVICES:
            _require(not service["public_endpoint_required"] and "domain" not in service and
                     "domain_key" not in service, f"Private service cannot be public: {name}")
        if service["public_endpoint_required"]:
            domain_key = service.get("domain_key")
            _require(domain_key in PUBLIC_KEYS and service.get("domain") == manifest["public_endpoints"][domain_key],
                     f"Invalid public service domain: {name}")
        _require(type(service.get("depends_on")) is list and
                 all(dependency in services for dependency in service["depends_on"]),
                 f"Invalid service dependencies: {name}")
    _require({service["domain_key"] for service in services.values() if service["public_endpoint_required"]}
             == PUBLIC_KEYS, "Public service domains do not match endpoints")
    _require(services["mailhog"].get("commercial_email_solution") is False,
             "MailHog cannot be a commercial email solution")

    variables = manifest["variables"]
    _keys(variables, ("secret_reference", "domain_binding", "internal_service_binding",
                      "environment_setting", "optional_integration"), "variables")
    secrets = _entries(variables["secret_reference"], "name", "secret_reference")
    _require(any(item.get("required") is True for item in secrets.values()), "Required secrets missing")
    for name, item in secrets.items():
        _keys(item, ("name", "services", "required", "source", "reference"), f"secret {name}")
        _keys(item["source"], ("kind", "key"), f"secret source {name}")
        _require(re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is not None and
                 item.get("reference") == f"runtime:{name}" and type(item.get("required")) is bool and
                 item["source"].get("key") == name and
                 item["source"].get("kind") in ("installation_secret", "runtime_secret"),
                 f"Invalid runtime secret reference: {name}")
    settings = _entries(variables["environment_setting"], "name", "environment_setting")
    for name, item in settings.items():
        _require(type(item.get("required")) is bool and "value" in item, f"Invalid setting: {name}")
        if identity["environment"] == "production":
            _require(item.get("status") == "resolved_by_commercial_policy" and item["value"] is not None,
                     f"Unresolved production setting: {name}")
    initialization = _entries(manifest["initialization"], "id", "initialization")
    checks = _entries(manifest["validation"], "id", "check")
    for check in checks.values():
        _require(type(check.get("required")) is bool, "Invalid check required flag")
    delivery = manifest["delivery"]
    _keys(delivery, ("ready", "release_rule", "required_check_ids", "pending_requirements"), "delivery")
    _require(delivery["ready"] is False and delivery["release_rule"] == "all_required_checks_pass",
             "Manifest delivery must start unready")
    required_checks = {name for name, item in checks.items() if item["required"]}
    ids = delivery["required_check_ids"]
    _require(type(ids) is list and len(ids) == len(set(ids)) and set(ids) == required_checks and
             bool(required_checks), "Invalid required_check_ids")
    expected_pending = {f"Resolve runtime secret reference: {name}" for name, item in secrets.items()
                        if item["required"]}
    expected_pending |= {f"Provide explicit runtime setting: {name}" for name, item in settings.items()
                         if item["required"] and item["value"] is None}
    expected_pending.add(CHECKS_PENDING)
    if identity["environment"] == "production":
        expected_pending.add(EMAIL_PENDING)
    pending = delivery["pending_requirements"]
    _require(type(pending) is list and len(pending) == len(set(pending)) and set(pending) == expected_pending,
             "Unknown or missing delivery requirement")
    try:
        manifest_fingerprint(manifest)
    except (TypeError, ValueError) as exc:
        raise ExecutorError("Manifest is not JSON serializable") from exc
    return services, secrets, settings, initialization, checks


def create_state(manifest):
    services, secrets, settings, initialization, checks = validate_manifest(manifest)
    identity = manifest["installation"]
    return {
        "state_version": 1,
        "installation": {name: identity[name] for name in ("installation_key", "slug", "environment")},
        "manifest_fingerprint": {"algorithm": "sha256", "value": manifest_fingerprint(manifest)},
        "phases": {phase: "pending" for phase in PHASES},
        "evidence": {
            "secrets": {name: False for name, item in secrets.items() if item["required"]},
            "settings": {name: False for name, item in settings.items()
                         if item["required"] and item["value"] is None},
            "services": {name: False for name in services},
            "initialization": {name: False for name in initialization},
            "checks": {name: None for name in checks},
            "commercial_email": False,
        },
        "audit": [],
        "delivery": {"ready": False},
    }


def validate_state(state, manifest):
    expected = create_state(manifest)
    _keys(state, expected, "state")
    _require(type(state["state_version"]) is int and state["state_version"] == 1,
             "Unsupported state_version")
    _keys(state["installation"], expected["installation"], "state installation")
    for field in expected["installation"]:
        _require(state["installation"][field] == expected["installation"][field],
                 f"State installation {field} mismatch")
    _keys(state["manifest_fingerprint"], ("algorithm", "value"), "fingerprint")
    _require(state["manifest_fingerprint"] == expected["manifest_fingerprint"],
             "Manifest fingerprint mismatch")
    _keys(state["phases"], PHASES, "phases")
    _require(all(type(value) is str and value in STATUSES for value in state["phases"].values()),
             "Invalid phase status")
    for index, phase in enumerate(PHASES):
        if state["phases"][phase] != "pending":
            _require(all(state["phases"][prior] == "completed" for prior in PHASES[:index]),
                     "Phase order violated")
    _keys(state["evidence"], expected["evidence"], "evidence")
    for category in ("secrets", "settings", "services", "initialization", "checks"):
        _keys(state["evidence"][category], expected["evidence"][category], category)
        for value in state["evidence"][category].values():
            _require(value is None or type(value) is bool if category == "checks" else type(value) is bool,
                     f"Invalid {category} evidence")
    _require(type(state["evidence"]["commercial_email"]) is bool, "Invalid commercial email evidence")
    _require(type(state["audit"]) is list, "Invalid audit")
    for sequence, event in enumerate(state["audit"], 1):
        _keys(event, ("sequence", "action", "phase", "subject", "result"), "audit event")
        _require(type(event["sequence"]) is int and event["sequence"] == sequence and
                 event["action"] in ("start", "complete", "block", "fail", "retry", "attest") and
                 event["phase"] in PHASES and type(event["subject"]) is str and
                 event["result"] in ("in_progress", "completed", "blocked", "failed", "pending", "true", "false"),
                 "Invalid audit event")
    replay = copy.deepcopy(expected)
    for event in state["audit"]:
        phase, action, subject, result = (event[name] for name in ("phase", "action", "subject", "result"))
        if action == "attest":
            _require(result in ("true", "false"), "Invalid attestation result")
            category = {"PREPARACAO": ("secrets", "settings"),
                        "INFRAESTRUTURA": ("services",),
                        "INICIALIZACAO": ("initialization",),
                        "VALIDACAO": ("checks",)}.get(phase, ())
            _require(replay["phases"][phase] == "in_progress", "Attestation outside active phase")
            if phase == "INFRAESTRUTURA" and subject == "commercial_email":
                _require(manifest["installation"]["environment"] == "production" and result == "true" and
                         not replay["evidence"]["commercial_email"], "Invalid commercial email attestation")
                replay["evidence"]["commercial_email"] = True
            else:
                matches = [name for name in category if subject in replay["evidence"][name]]
                _require(len(matches) == 1, "Unknown audit evidence")
                name = matches[0]
                value = result == "true"
                _require(name == "checks" or value, "Only check results may be false")
                _require(replay["evidence"][name][subject] != value, "Duplicate audit evidence")
                replay["evidence"][name][subject] = value
            continue
        _require(subject == phase, "Audit phase subject mismatch")
        current = replay["phases"][phase]
        if action == "start":
            _require(phase != "ENTREGA" and current == "pending" and result == "in_progress" and
                     all(replay["phases"][prior] == "completed" for prior in PHASES[:PHASES.index(phase)]),
                     "Invalid audited phase start")
        elif action == "complete":
            _require(result == "completed", "Invalid audited completion")
            if phase == "ENTREGA":
                _require(current == "pending" and not delivery_blockers(replay, manifest),
                         "Invalid audited delivery")
                replay["delivery"]["ready"] = True
            else:
                _require(current == "in_progress", "Invalid audited completion")
                if phase == "PREPARACAO":
                    _require(all(replay["evidence"]["secrets"].values()) and
                             all(replay["evidence"]["settings"].values()),
                             "Audited preparation requirements incomplete")
                elif phase == "INFRAESTRUTURA":
                    _require(all(replay["evidence"]["services"].values()), "Audited services incomplete")
                elif phase == "INICIALIZACAO":
                    _require(all(replay["evidence"]["initialization"].values()), "Audited initialization incomplete")
                elif phase == "VALIDACAO":
                    _require(all(value is not None for value in replay["evidence"]["checks"].values()),
                             "Audited checks incomplete")
        elif action in ("block", "fail"):
            _require(phase != "ENTREGA" and current == "in_progress" and
                     result == ("blocked" if action == "block" else "failed"), "Invalid audited failure")
        elif action == "retry":
            _require(phase != "ENTREGA" and current in ("blocked", "failed") and result == "pending",
                     "Invalid audited retry")
        else:
            raise ExecutorError("Invalid audit action")
        replay["phases"][phase] = result
    _require(replay["phases"] == state["phases"] and replay["evidence"] == state["evidence"] and
             replay["delivery"] == state["delivery"], "State does not match audit")
    _keys(state["delivery"], ("ready",), "state delivery")
    _require(type(state["delivery"]["ready"]) is bool, "Invalid delivery readiness")
    completed = state["phases"]["ENTREGA"] == "completed"
    _require(state["delivery"]["ready"] == completed, "Delivery status mismatch")
    if completed:
        _require(not delivery_blockers(state, manifest), "Delivery gates not satisfied")
    return True


def resume_state(state, manifest):
    validate_state(state, manifest)
    return copy.deepcopy(state)


def _event(state, action, phase, subject, result):
    state["audit"].append({"sequence": len(state["audit"]) + 1, "action": action,
                           "phase": phase, "subject": subject, "result": result})


def _change_phase(state, manifest, phase, action):
    validate_state(state, manifest)
    _require(phase in PHASES, "Unknown phase")
    _require(phase != "ENTREGA", "Use complete_delivery for ENTREGA")
    output = copy.deepcopy(state)
    current = output["phases"][phase]
    if action == "start":
        if current in ("in_progress", "completed"):
            return output
        _require(current == "pending", "Blocked or failed phase requires explicit retry")
        _require(all(output["phases"][prior] == "completed" for prior in PHASES[:PHASES.index(phase)]),
                 "Previous phase is not completed")
        target = "in_progress"
    elif action == "complete":
        if current == "completed":
            return output
        _require(current == "in_progress", "Phase must be in progress")
        evidence = output["evidence"]
        if phase == "PREPARACAO":
            _require(all(evidence["secrets"].values()) and all(evidence["settings"].values()),
                     "Preparation secrets or runtime settings lack evidence")
        elif phase == "INFRAESTRUTURA":
            _require(all(evidence["services"].values()), "Infrastructure services lack evidence")
        elif phase == "INICIALIZACAO":
            _require(all(evidence["initialization"].values()), "Initialization steps lack evidence")
        elif phase == "VALIDACAO":
            _require(all(value is not None for value in evidence["checks"].values()),
                     "Validation checks lack results")
        target = "completed"
    elif action in ("block", "fail"):
        target = "blocked" if action == "block" else "failed"
        if current == target:
            return output
        _require(current == "in_progress", "Only an active phase can be blocked or failed")
    elif action == "retry":
        _require(current in ("blocked", "failed"), "Only a blocked or failed phase can be retried")
        target = "pending"
    else:
        raise ExecutorError("Unknown transition")
    output["phases"][phase] = target
    _event(output, action, phase, phase, target)
    return output


def start_phase(state, manifest, phase):
    return _change_phase(state, manifest, phase, "start")


def complete_phase(state, manifest, phase):
    return _change_phase(state, manifest, phase, "complete")


def block_phase(state, manifest, phase):
    return _change_phase(state, manifest, phase, "block")


def fail_phase(state, manifest, phase):
    return _change_phase(state, manifest, phase, "fail")


def retry_phase(state, manifest, phase):
    return _change_phase(state, manifest, phase, "retry")


def _attest(state, manifest, category, name, result, phase):
    validate_state(state, manifest)
    _require(type(name) is str and name in state["evidence"][category], f"Unknown {category} identifier")
    _require(type(result) is bool, "Evidence result must be boolean")
    output = copy.deepcopy(state)
    if output["evidence"][category][name] == result:
        return output
    _require(state["phases"][phase] == "in_progress", f"{phase} must be in progress")
    output["evidence"][category][name] = result
    _event(output, "attest", phase, name, str(result).lower())
    return output


def attest_secret(state, manifest, name):
    return _attest(state, manifest, "secrets", name, True, "PREPARACAO")


def attest_setting(state, manifest, name):
    return _attest(state, manifest, "settings", name, True, "PREPARACAO")


def attest_service(state, manifest, name):
    return _attest(state, manifest, "services", name, True, "INFRAESTRUTURA")


def attest_initialization(state, manifest, step_id):
    return _attest(state, manifest, "initialization", step_id, True, "INICIALIZACAO")


def record_check(state, manifest, check_id, passed):
    return _attest(state, manifest, "checks", check_id, passed, "VALIDACAO")


def attest_commercial_email(state, manifest):
    validate_state(state, manifest)
    _require(manifest["installation"]["environment"] == "production", "Commercial email is production only")
    _require(state["phases"]["INFRAESTRUTURA"] == "in_progress", "INFRAESTRUTURA must be in progress")
    output = copy.deepcopy(state)
    if not output["evidence"]["commercial_email"]:
        output["evidence"]["commercial_email"] = True
        _event(output, "attest", "INFRAESTRUTURA", "commercial_email", "true")
    return output


def delivery_blockers(state, manifest):
    """Derive outstanding mandatory gates; caller validates state for untrusted input."""
    evidence = state["evidence"]
    blockers = []
    for phase in PHASES[:-1]:
        if state["phases"][phase] != "completed":
            blockers.append(f"phase:{phase}")
    blockers += [f"secret:{name}" for name, ready in evidence["secrets"].items() if not ready]
    blockers += [f"setting:{name}" for name, ready in evidence["settings"].items() if not ready]
    blockers += [f"service:{name}" for name, ready in evidence["services"].items() if not ready]
    blockers += [f"initialization:{name}" for name, ready in evidence["initialization"].items() if not ready]
    blockers += [f"check:{name}" for name in manifest["delivery"]["required_check_ids"]
                 if evidence["checks"][name] is not True]
    if manifest["installation"]["environment"] == "production" and not evidence["commercial_email"]:
        blockers.append("commercial_email")
    return blockers


def complete_delivery(state, manifest):
    validate_state(state, manifest)
    output = copy.deepcopy(state)
    if output["phases"]["ENTREGA"] == "completed":
        return output
    _require(not delivery_blockers(output, manifest), "Delivery gates blocked: " +
             ", ".join(delivery_blockers(output, manifest)))
    output["phases"]["ENTREGA"] = "completed"
    output["delivery"]["ready"] = True
    _event(output, "complete", "ENTREGA", "ENTREGA", "completed")
    return output
