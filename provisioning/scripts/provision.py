#!/usr/bin/env python3
"""Local validation and deterministic dry-run only. No provisioning side effects."""

import argparse
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
REFERENCE_PATTERN = re.compile(r"^runtime:[A-Z][A-Z0-9_]*$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
HOST_PATTERN = re.compile(r"^(?:[a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+$")
UNSAFE_WORDS = {"example", "placeholder", "changeme", "dummy", "localhost", "test", "invalid"}


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArtGenial provisioning: local validation and dry-run only")
    parser.add_argument("command", choices=["validate", "plan"])
    parser.add_argument("--config", type=Path, default=EXAMPLE)
    args = parser.parse_args(argv)
    try:
        contract, catalog, checks = load_json(CONTRACT), load_json(CATALOG), load_json(CHECKS)
        config = load_json(args.config)
        errors = validate(config, contract, catalog, checks)
    except ConfigurationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 2
    if args.command == "validate":
        print("VALID: installation configuration (local checks only)")
    else:
        print(plan(config, catalog, checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
