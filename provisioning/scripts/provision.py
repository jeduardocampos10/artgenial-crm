#!/usr/bin/env python3
"""Local validation and deterministic dry-run only. No provisioning side effects."""

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "installation.contract.json"
CATALOG = ROOT / "config" / "services.json"
CHECKS = ROOT / "checks" / "required.json"
EXAMPLE = ROOT / "config" / "installation.example.json"
DEPLOYMENT_VARIABLES = ROOT / "config" / "deployment.variables.json"
COMMERCIAL_RUNTIME = ROOT / "config" / "commercial.runtime.json"
REFERENCE_PATTERN = re.compile(r"^runtime:[A-Z][A-Z0-9_]*$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
HOST_PATTERN = re.compile(r"^(?:[a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+$")
UNSAFE_WORDS = {"example", "placeholder", "changeme", "dummy", "localhost", "test", "invalid"}
VARIABLE_CLASSES = (
    "secret_reference", "domain_binding", "internal_service_binding",
    "environment_setting", "optional_integration",
)
DOMAIN_BINDINGS = {
    "FRONTEND_URL": "frontend", "BACKEND_URL": "crm_api",
    "AUTH_SERVICE_URL": "auth_api", "CORS_ORIGINS": "frontend",
    "API_URL": "processor_api", "APP_URL": "frontend",
    "VITE_API_URL": "crm_api", "VITE_AUTH_API_URL": "auth_api",
    "VITE_WS_URL": "crm_api", "VITE_EVOAI_API_URL": "core_api",
    "VITE_AGENT_PROCESSOR_URL": "processor_api", "VITE_EVOFLOW_API_URL": "flow_api",
}
ENVIRONMENT_SETTINGS = {
    "RAILS_ENV", "VITE_APP_ENV", "DEBUG", "EVO_FLOW_ENABLED",
    "EVO_FLOW_ALLOW_INSECURE", "ACTIVE_STORAGE_SERVICE", "AI_PROCESSOR_VERSION",
    "LISTEN_ADDR", "MEDIA_HOST_ALLOWLIST", "AI_CALL_TIMEOUT_SECONDS",
    "DOORKEEPER_JWT_ALGORITHM", "DOORKEEPER_JWT_ISS",
    "POSTGRES_DATABASE", "POSTGRES_USERNAME",
}
COMMERCIAL_FIXED_SETTINGS = {
    "RAILS_ENV": "production",
    "VITE_APP_ENV": "production",
    "DEBUG": False,
    "EVO_FLOW_ENABLED": True,
    "EVO_FLOW_ALLOW_INSECURE": False,
    "ACTIVE_STORAGE_SERVICE": "local",
    "AI_PROCESSOR_VERSION": "v1",
    "LISTEN_ADDR": "0.0.0.0:8080",
    "AI_CALL_TIMEOUT_SECONDS": 90,
    "DOORKEEPER_JWT_ALGORITHM": "hs256",
    "DOORKEEPER_JWT_ISS": "evo-auth-service",
    "POSTGRES_USERNAME": "postgres",
}
COMMERCIAL_DERIVED_SETTINGS = {
    "POSTGRES_DATABASE": "database_from_slug_v1",
    "MEDIA_HOST_ALLOWLIST": "hostname_from_crm_api_v1",
}
PRIVATE_SERVICES = {"postgres", "redis", "rabbitmq", "clickhouse", "evo-bot-runtime", "mailhog"}


class ConfigurationError(ValueError):
    """Configuration is invalid or cannot be read safely."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            return json.load(source, object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read JSON file {path}: {exc}") from exc


def _object(value, name, errors):
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object")
        return {}
    return value


def _required_string(value, name, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return ""
    return value.strip()


def _placeholder(value):
    lowered = value.lower()
    tokens = set(re.split(r"[^a-z0-9]+", lowered))
    return bool(tokens & UNSAFE_WORDS) or "<" in value or ">" in value


def validate(config, contract, catalog, checks):
    """Return all local validation errors; never connect to external systems."""
    errors = []
    config = _object(config, "installation", errors)
    if not config:
        return errors or ["installation must not be empty"]

    required = set(contract["required_fields"])
    for field in sorted(required - config.keys()):
        errors.append(f"Missing required field: {field}")
    for field in sorted(config.keys() - required):
        errors.append(f"Unknown field: {field}")

    if type(config.get("schema_version")) is not int or config["schema_version"] != contract["schema_version"]:
        errors.append(f"schema_version must be {contract['schema_version']}")
    name = _required_string(config.get("installation_name"), "installation_name", errors)
    slug = _required_string(config.get("slug"), "slug", errors)
    if slug and not re.fullmatch(contract["slug_pattern"], slug):
        errors.append("slug must use lowercase letters, digits and single hyphens")
    key = _required_string(config.get("installation_key"), "installation_key", errors)
    try:
        if str(uuid.UUID(key)) != key.lower():
            raise ValueError("non-canonical UUID")
    except ValueError:
        errors.append("installation_key must be a canonical UUID")

    environment = config.get("environment")
    if environment not in contract["environments"]:
        errors.append(f"environment must be one of: {', '.join(contract['environments'])}")
    production = environment == "production"
    if production and (slug in {"demo", "test", "example", "cliente-ficticio"} or _placeholder(name)):
        errors.append("production identity contains an example or placeholder")
    if production and key == load_json(EXAMPLE)["installation_key"]:
        errors.append("production installation_key cannot reuse the example UUID")

    domains = _object(config.get("domains"), "domains", errors)
    expected_domains = set(contract["required_domains"])
    for domain_key in sorted(expected_domains - domains.keys()):
        errors.append(f"Missing public domain: {domain_key}")
    for domain_key in sorted(domains.keys() - expected_domains):
        errors.append(f"Unknown public domain: {domain_key}")
    seen_hosts = {}
    for domain_key in sorted(expected_domains & domains.keys()):
        value = _required_string(domains[domain_key], f"domains.{domain_key}", errors)
        if not value:
            continue
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            host, port, parsed = None, None, None
        if (not parsed or parsed.scheme not in {"http", "https"} or not host
                or not HOST_PATTERN.fullmatch(host) or parsed.username or parsed.password
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            errors.append(f"domains.{domain_key} must be a public HTTP(S) origin without path or credentials")
            continue
        host = host.lower()
        if host in seen_hosts:
            errors.append(f"Duplicate public domain: {domain_key} and {seen_hosts[host]}")
        seen_hosts[host] = domain_key
        if production and (parsed.scheme != "https" or (port is not None and port != 443)
                           or host == "localhost" or host.endswith((".test", ".local", ".invalid"))
                           or host.endswith((".example", ".example.com", ".example.org"))
                           or _placeholder(host)):
            errors.append(f"domains.{domain_key} is unsafe for production")

    administrator = _object(config.get("administrator"), "administrator", errors)
    for field in contract["administrator_fields"]:
        _required_string(administrator.get(field), f"administrator.{field}", errors)
    for field in sorted(administrator.keys() - set(contract["administrator_fields"])):
        errors.append(f"Unknown administrator field: {field}; passwords must be supplied at runtime")
    email = administrator.get("email")
    if isinstance(email, str) and email and not EMAIL_PATTERN.fullmatch(email):
        errors.append("administrator.email must be an email address")
    if production and isinstance(email, str) and _placeholder(email.split("@")[-1]):
        errors.append("administrator.email is unsafe for production")

    services = config.get("required_services")
    catalog_services = catalog["services"]
    names = [service["name"] for service in catalog_services]
    if not isinstance(services, list) or any(not isinstance(item, str) for item in services):
        errors.append("required_services must be an array of service names")
    else:
        if len(services) != len(set(services)):
            errors.append("required_services contains duplicates")
        if set(services) != set(names):
            errors.append("required_services must match the complete service catalog")
    if len(names) != len(set(names)):
        errors.append("service catalog contains duplicate names")
    public_domains = {service.get("domain_key") for service in catalog_services if service["public_endpoint_required"]}
    if public_domains != expected_domains:
        errors.append("service catalog public domains differ from installation contract")
    for service in catalog_services:
        if not set(service["depends_on"]).issubset(names):
            errors.append(f"Unknown dependency in service catalog: {service['name']}")

    references = _object(config.get("secret_references"), "secret_references", errors)
    for reference in sorted(set(contract["required_secret_references"]) - references.keys()):
        errors.append(f"Missing secret reference: {reference}")
    for reference, value in references.items():
        if not isinstance(reference, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", reference):
            errors.append("secret_references contains an invalid variable name")
        if not isinstance(value, str) or not REFERENCE_PATTERN.fullmatch(value) or value != f"runtime:{reference}":
            errors.append(f"secret_references.{reference} must be a runtime reference, never a value")

    check_list = checks["checks"]
    check_ids = [check["id"] for check in check_list]
    if len(check_ids) != len(set(check_ids)):
        errors.append("checks catalog contains duplicate IDs")
    for check in check_list:
        if check["domain_key"] not in expected_domains:
            errors.append(f"Unknown domain in check: {check['id']}")
    return errors


def plan(config, catalog, checks):
    """Render intended actions only. Caller must validate first."""
    lines = [
        "PREPARAÇÃO",
        f"  Identificar instalação {config['slug']} ({config['installation_key']})",
        "  Receber secrets exclusivos e credenciais do administrador em runtime; não exibir valores",
        "INFRAESTRUTURA",
    ]
    for service in catalog["services"]:
        port = service["internal_port"] if service["internal_port"] is not None else "sem porta HTTP"
        public = f"; público: {config['domains'][service['domain_key']]}" if service["public_endpoint_required"] else ""
        dependencies = ", ".join(service["depends_on"]) or "nenhuma"
        lines.append(f"  Preparar {service['name']} (porta interna {port}; depende de {dependencies}{public})")
    lines.extend([
        "INICIALIZAÇÃO",
        "  Planejar migrations por serviço somente na nova instalação isolada",
        "  Verificar/inicializar RuntimeConfig.account do Auth de forma idempotente (integração futura)",
        "  Criar administrador inicial com credencial fornecida em runtime (integração futura)",
        f"  Aplicar artgenial.base v1 pelo Applier existente com installation_key {config['installation_key']} (integração futura)",
        "VALIDAÇÃO",
    ])
    for check in checks["checks"]:
        domain = config["domains"][check["domain_key"]].rstrip("/")
        # Frontend bindings retain the HTTP(S) origin; only upgrade checks use WS(S).
        if check["kind"] == "websocket_upgrade":
            domain = ("wss://" if domain.startswith("https://") else "ws://") + domain.split("://", 1)[1]
        target = domain + check.get("path", "")
        variable = f" [{check['variable']}]" if "variable" in check else ""
        lines.append(f"  Verificar {check['id']}{variable}: {target} ({check['kind']})")
    lines.extend(["ENTREGA", "  Liberar CRM somente após todos os checks obrigatórios passarem"])
    return "\n".join(lines)


def validate_deployment_catalog(variables_catalog, contract, catalog, checks):
    """Reject unsafe or ambiguous deployment mappings before emitting a manifest."""
    errors = []
    if (not isinstance(variables_catalog, dict)
            or type(variables_catalog.get("catalog_version")) is not int
            or variables_catalog["catalog_version"] != 1):
        return ["deployment variables catalog_version must be 1"]
    if set(variables_catalog) != {"catalog_version", "variables"}:
        errors.append("deployment variables catalog contains unsupported fields")
    items = variables_catalog.get("variables")
    if not isinstance(items, list):
        return ["deployment variables must be an array"]
    services = {item["name"]: item for item in catalog["services"]}
    names = set()
    mapped_domains = {}
    settings = set()
    secrets = {}
    optional = {}
    expected_source_keys = {
        "secret_reference": {"installation_secret": {"kind", "key"}, "runtime_secret": {"kind", "key"}},
        "domain_binding": {"domain": {"kind", "key"}},
        "internal_service_binding": {"service": {"kind", "service", "format", "scheme", "path"}},
        "environment_setting": {"runtime_setting": {"kind", "key"}},
        "optional_integration": {"runtime_optional": {"kind", "key"}},
    }
    for item in items:
        if not isinstance(item, dict):
            errors.append("deployment variable entries must be objects")
            continue
        name = item.get("name")
        classification = item.get("classification")
        source = item.get("source")
        targets = item.get("services")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            errors.append("deployment variable name must be uppercase")
            continue
        if name in names:
            errors.append(f"Duplicate deployment variable: {name}")
        names.add(name)
        if classification not in VARIABLE_CLASSES:
            errors.append(f"Invalid classification for {name}")
            continue
        if type(item.get("required")) is not bool:
            errors.append(f"{name}.required must be boolean")
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(target, str) or target not in services for target in targets)):
            errors.append(f"{name}.services must name catalog services")
        if not isinstance(source, dict):
            errors.append(f"{name}.source must be an object")
            continue
        kind = source.get("kind")
        allowed = expected_source_keys[classification]
        if kind not in allowed or set(source) - allowed.get(kind, set()):
            errors.append(f"{name}.source contains an unsupported mapping or literal value")
            continue
        allowed_item_keys = {"name", "classification", "services", "required", "source"}
        if name == "AUTH_APIKEY_INTEGRATION_LOCAL":
            allowed_item_keys.add("required_in_production")
        if set(item) - allowed_item_keys:
            errors.append(f"{name} contains unsupported fields")
        if classification == "secret_reference":
            secrets[name] = item
            if source.get("key") != name:
                errors.append(f"{name} secret reference key must match its name")
        elif classification == "domain_binding":
            mapped_domains[name] = source.get("key")
            if source.get("key") not in contract["required_domains"]:
                errors.append(f"{name} refers to an unknown public domain")
        elif classification == "internal_service_binding":
            target = services.get(source.get("service"))
            format_name = source.get("format")
            if not target or target["internal_port"] is None or format_name not in {"url", "host", "port"}:
                errors.append(f"{name} requires a service with an internal port and valid format")
            if format_name == "url":
                path = source.get("path", "")
                if (source.get("scheme") not in {"http", "amqp"} or not isinstance(path, str)
                        or (path and not path.startswith("/")) or "?" in path or "#" in path):
                    errors.append(f"{name} has an invalid internal URL source")
            elif "scheme" in source or "path" in source:
                errors.append(f"{name} host/port binding cannot have scheme or path")
        elif classification == "environment_setting":
            settings.add(name)
            if source.get("key") != name:
                errors.append(f"{name} runtime setting key must match its name")
        else:
            optional[name] = item
            if source.get("key") != name or item.get("required"):
                errors.append(f"{name} optional integration must be an optional runtime reference")
    for name in contract["required_secret_references"]:
        item = secrets.get(name)
        if not item or item["source"].get("kind") != "installation_secret" or not item.get("required"):
            errors.append(f"Required installation secret missing from deployment catalog: {name}")
    integration_key = secrets.get("AUTH_APIKEY_INTEGRATION_LOCAL")
    if (not integration_key or integration_key["source"].get("kind") != "runtime_secret"
            or integration_key.get("required_in_production") is not True):
        errors.append("AUTH_APIKEY_INTEGRATION_LOCAL must require a runtime secret in production")
    if mapped_domains != DOMAIN_BINDINGS:
        errors.append("Deployment domain bindings do not match the approved mapping")
    if settings != ENVIRONMENT_SETTINGS:
        errors.append("Deployment environment settings do not match the Compose catalog")
    if set(optional) != {"VITE_TINYMCE_API_KEY"}:
        errors.append("VITE_TINYMCE_API_KEY must be the optional integration")
    for name in PRIVATE_SERVICES:
        service = services.get(name)
        if not service or service["public_endpoint_required"] or "domain_key" in service:
            errors.append(f"Internal service must remain private: {name}")
    if any("host_port" in service or "host_ports" in service or "ports" in service for service in services.values()):
        errors.append("Deployment service catalog must not expose host ports")
    if "mailhog" in services and "local" not in services["mailhog"]["role"].lower():
        errors.append("MailHog must remain a local testing tool")
    checks_by_id = {check["id"]: check for check in checks["checks"]}
    ws_binding = checks_by_id.get("vite_ws_url", {})
    ws_upgrade = checks_by_id.get("crm_websocket", {})
    if (ws_binding.get("kind") != "frontend_binding" or ws_binding.get("domain_key") != "crm_api"
            or "path" in ws_binding or ws_upgrade.get("kind") != "websocket_upgrade"
            or ws_upgrade.get("domain_key") != "crm_api" or ws_upgrade.get("path") != "/cable"):
        errors.append("WebSocket binding and upgrade checks must remain separate")
    return errors


def _internal_value(source, services):
    service = services[source["service"]]
    if source["format"] == "host":
        return service["name"]
    if source["format"] == "port":
        return str(service["internal_port"])
    return f"{source['scheme']}://{service['name']}:{service['internal_port']}{source.get('path', '')}"


def validate_commercial_policy(policy):
    """Accept only the approved, secret-free production runtime policy."""
    if not isinstance(policy, dict) or set(policy) != {"policy_version", "environment", "settings"}:
        return ["commercial runtime policy must contain only policy_version, environment and settings"]
    errors = []
    if type(policy["policy_version"]) is not int or policy["policy_version"] != 1:
        errors.append("commercial runtime policy_version must be 1")
    if policy["environment"] != "production":
        errors.append("commercial runtime policy environment must be production")
    settings = policy["settings"]
    if not isinstance(settings, dict):
        return errors + ["commercial runtime settings must be an object"]
    if set(settings) != ENVIRONMENT_SETTINGS:
        errors.append("commercial runtime settings must exactly match ENVIRONMENT_SETTINGS")
    for name, expected in COMMERCIAL_FIXED_SETTINGS.items():
        setting = settings.get(name)
        if (not isinstance(setting, dict) or set(setting) != {"kind", "value"}
                or setting.get("kind") != "fixed" or type(setting.get("value")) is not type(expected)
                or setting.get("value") != expected):
            errors.append(f"commercial runtime {name} must use the approved fixed value")
    for name, rule in COMMERCIAL_DERIVED_SETTINGS.items():
        setting = settings.get(name)
        if not isinstance(setting, dict) or setting != {"kind": "derived", "rule": rule}:
            errors.append(f"commercial runtime {name} must use approved derivation {rule}")
    return errors


def _commercial_database(slug):
    """PostgreSQL identifier: injective for short slugs, stable suffix for long ones."""
    candidate = "artgenial_" + slug.replace("-", "_")
    if len(candidate) <= 63:
        return candidate
    digest = hashlib.sha256(slug.encode("ascii")).hexdigest()[:12]
    return f"{candidate[:50]}_{digest}"


def _commercial_setting(name, config, policy):
    setting = policy["settings"][name]
    source = {"kind": "commercial_runtime_policy", "policy_version": policy["policy_version"], "setting": name}
    if setting["kind"] == "fixed":
        return setting["value"], source
    source["kind"] = "commercial_runtime_derivation"
    source["rule"] = setting["rule"]
    if name == "POSTGRES_DATABASE":
        source["input"] = "installation.slug"
        return _commercial_database(config["slug"]), source
    source["input"] = "installation.domains.crm_api"
    return urlsplit(config["domains"]["crm_api"]).hostname, source


def build_manifest(config, catalog, checks, variables_catalog, commercial_policy=None):
    """Build data only; caller validates first and decides whether to print it."""
    services = {service["name"]: service for service in catalog["services"]}
    infrastructure = []
    for service in catalog["services"]:
        item = {key: service[key] for key in (
            "name", "role", "internal_port", "depends_on", "volumes", "public_endpoint_required"
        )}
        if "additional_internal_ports" in service:
            item["additional_internal_ports"] = service["additional_internal_ports"]
        if service["public_endpoint_required"]:
            item["domain_key"] = service["domain_key"]
            item["domain"] = config["domains"][service["domain_key"]]
        if service["name"] == "mailhog":
            item["commercial_email_solution"] = False
        infrastructure.append(item)

    variables = {classification: [] for classification in VARIABLE_CLASSES}
    production = config["environment"] == "production"
    if production:
        errors = validate_commercial_policy(commercial_policy)
        if errors:
            raise ConfigurationError("; ".join(errors))
    pending = []
    for item in sorted(variables_catalog["variables"], key=lambda item: item["name"]):
        source = item["source"]
        entry = {
            "name": item["name"], "services": item["services"],
            "required": item["required"] or (production and item.get("required_in_production", False)),
            "source": source,
        }
        classification = item["classification"]
        if classification == "secret_reference":
            entry["reference"] = (config["secret_references"][item["name"]]
                                  if source["kind"] == "installation_secret"
                                  else f"runtime:{item['name']}")
            if entry["required"]:
                pending.append(f"Resolve runtime secret reference: {item['name']}")
        elif classification == "domain_binding":
            entry["value"] = config["domains"][source["key"]].rstrip("/")
        elif classification == "internal_service_binding":
            entry["value"] = _internal_value(source, services)
        elif classification == "environment_setting" and production:
            entry["value"], entry["source"] = _commercial_setting(item["name"], config, commercial_policy)
            entry["status"] = "resolved_by_commercial_policy"
        else:
            entry["value"] = None
            entry["status"] = "explicit_runtime_value_required" if entry["required"] else "optional_unconfigured"
            if entry["required"]:
                pending.append(f"Provide explicit runtime setting: {item['name']}")
        variables[classification].append(entry)

    validation = []
    for check in checks["checks"]:
        domain = config["domains"][check["domain_key"]].rstrip("/")
        if check["kind"] == "websocket_upgrade":
            domain = ("wss://" if domain.startswith("https://") else "ws://") + domain.split("://", 1)[1]
        entry = dict(check)
        entry["target"] = domain + check.get("path", "")
        entry["executed"] = False
        validation.append(entry)
    if production:
        pending.append("Select a commercial email solution; MailHog is for local testing only")
    pending.append("Execute and pass all required public and account checks")
    return {
        "manifest_version": 1,
        "installation": {key: config[key] for key in (
            "installation_name", "slug", "installation_key", "environment"
        )},
        "infrastructure": infrastructure,
        "public_endpoints": {key: config["domains"][key].rstrip("/") for key in sorted(config["domains"])},
        "variables": variables,
        "initialization": [
            {"id": "migrations", "action": "run_for_new_isolated_installation", "executed": False},
            {"id": "auth_account", "action": "ensure_RuntimeConfig.account_idempotently", "executed": False},
            {"id": "initial_administrator", "action": "create_with_runtime_credential", "executed": False},
            {"id": "artgenial_base", "action": "apply_existing_Applier", "template_key": "artgenial.base",
             "template_version": "1", "installation_key": config["installation_key"], "executed": False},
        ],
        "validation": validation,
        "delivery": {"ready": False, "release_rule": "all_required_checks_pass",
                     "required_check_ids": sorted(check["id"] for check in checks["checks"] if check["required"]),
                     "pending_requirements": sorted(pending)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArtGenial provisioning: local validation, plan and manifest only")
    parser.add_argument("command", choices=["validate", "plan", "manifest"])
    parser.add_argument("--config", type=Path, default=EXAMPLE)
    args = parser.parse_args(argv)
    commercial_policy = None
    try:
        contract, catalog, checks = load_json(CONTRACT), load_json(CATALOG), load_json(CHECKS)
        config = load_json(args.config)
        errors = validate(config, contract, catalog, checks)
        if args.command == "manifest" and not errors:
            variables_catalog = load_json(DEPLOYMENT_VARIABLES)
            errors = validate_deployment_catalog(variables_catalog, contract, catalog, checks)
            if not errors and config["environment"] == "production":
                commercial_policy = load_json(COMMERCIAL_RUNTIME)
                errors = validate_commercial_policy(commercial_policy)
    except ConfigurationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 2
    if args.command == "validate":
        print("VALID: installation configuration (local checks only)")
    elif args.command == "plan":
        print(plan(config, catalog, checks))
    else:
        print(json.dumps(build_manifest(config, catalog, checks, variables_catalog, commercial_policy),
                         ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
