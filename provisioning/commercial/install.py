#!/usr/bin/env python3
"""Portable Compose installer. Runtime credentials never enter the manifest or state."""

import argparse
import getpass
import json
import os
import re
import shutil
import smtplib
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from provisioning.scripts import executor, provision


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = Path(__file__).with_name("compose.yaml")
RUNTIME_KEYS = set(provision.load_json(provision.CONTRACT)["required_secret_references"]) | {
    "AUTH_APIKEY_INTEGRATION_LOCAL", "RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS",
    "CLICKHOUSE_PASSWORD", "SMTP_ADDRESS", "SMTP_PORT", "SMTP_USERNAME",
    "SMTP_PASSWORD", "MAILER_SENDER_EMAIL",
}
SECRET_KEYS = {key for key in RUNTIME_KEYS if any(word in key for word in ("PASSWORD", "SECRET", "TOKEN", "APIKEY"))}
SMTP_KEYS = {"SMTP_ADDRESS", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "MAILER_SENDER_EMAIL",
             "SMTP_SSL", "SMTP_ENABLE_STARTTLS_AUTO", "SMTP_AUTHENTICATION"}
SMTP_SERVICES = {"evo-auth", "evo-auth-sidekiq", "evo-crm", "evo-crm-sidekiq"}
EXTRA_SERVICE_KEYS = {
    "rabbitmq": {"RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS"},
    "clickhouse": {"CLICKHOUSE_PASSWORD"},
    "evo-flow": {"RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS", "CLICKHOUSE_PASSWORD"},
}
HOST_ENV_KEYS = {"PATH", "Path", "PATHEXT", "SystemRoot", "SYSTEMROOT", "WINDIR", "HOME",
                 "USERPROFILE", "TEMP", "TMP", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG",
                 "SSL_CERT_FILE"}


class InstallError(RuntimeError):
    pass


def read_runtime(path):
    path = path.resolve(strict=True)
    if ROOT == path or ROOT in path.parents:
        raise InstallError("Runtime file must be outside the repository")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise InstallError("Runtime file must be owner-only (chmod 600)")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in values:
            raise InstallError("Invalid or duplicate runtime variable")
        if key not in RUNTIME_KEYS | {"SMTP_SSL", "SMTP_ENABLE_STARTTLS_AUTO", "SMTP_AUTHENTICATION"}:
            raise InstallError(f"Unsupported runtime variable: {key}")
        if "\n" in value or "\r" in value or "$" in value:
            raise InstallError(f"Unsupported runtime value syntax: {key}")
        values[key] = value
    missing = sorted(key for key in RUNTIME_KEYS if not values.get(key))
    if missing:
        raise InstallError("Missing runtime variables: " + ", ".join(missing))
    if values["SMTP_ADDRESS"].lower() in {"localhost", "127.0.0.1", "mailhog"}:
        raise InstallError("A commercial SMTP host is required")
    if (not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", values["SMTP_ADDRESS"])
            or values["SMTP_ADDRESS"].lower().endswith((".test", ".local", ".invalid", ".example"))):
        raise InstallError("SMTP_ADDRESS must be an external hostname")
    if values.get("SMTP_SSL", "false").lower() not in {"true", "false"}:
        raise InstallError("SMTP_SSL must be true or false")
    try:
        port = int(values["SMTP_PORT"])
    except ValueError as exc:
        raise InstallError("SMTP_PORT must be an integer") from exc
    if not 1 <= port <= 65535 or "@" not in values["MAILER_SENDER_EMAIL"]:
        raise InstallError("Invalid commercial SMTP configuration")
    for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", values[key]):
            raise InstallError(f"{key} must use URL-safe characters")
    if any(not values[key] for key in SECRET_KEYS):
        raise InstallError("Runtime secrets cannot be empty")
    return values


def verify_smtp(runtime):
    """Prove the configured remote SMTP server accepts the runtime credentials."""
    host, port = runtime["SMTP_ADDRESS"], int(runtime["SMTP_PORT"])
    try:
        if runtime.get("SMTP_SSL", "false").lower() == "true":
            connection = smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context())
        else:
            connection = smtplib.SMTP(host, port, timeout=15)
        with connection:
            connection.ehlo()
            if runtime.get("SMTP_SSL", "false").lower() != "true":
                connection.starttls(context=ssl.create_default_context())
                connection.ehlo()
            connection.login(runtime["SMTP_USERNAME"], runtime["SMTP_PASSWORD"])
    except (OSError, smtplib.SMTPException) as exc:
        raise InstallError("Commercial SMTP verification failed") from None


def prepare(config_path, runtime_path, state_path):
    config = provision.load_json(config_path)
    contract, catalog, checks = map(provision.load_json, (provision.CONTRACT, provision.CATALOG, provision.CHECKS))
    errors = provision.validate(config, contract, catalog, checks)
    variables = provision.load_json(provision.DEPLOYMENT_VARIABLES)
    errors += provision.validate_deployment_catalog(variables, contract, catalog, checks)
    policy = provision.load_json(provision.COMMERCIAL_RUNTIME)
    errors += provision.validate_commercial_policy(policy)
    if config.get("environment") != "production":
        errors.append("Commercial installer requires production")
    if errors:
        raise InstallError("Invalid installation: " + "; ".join(errors))
    manifest = provision.build_manifest(config, catalog, checks, variables, policy)
    executor.validate_manifest(manifest)
    runtime = read_runtime(runtime_path)
    if state_path.exists():
        state = executor.resume_state(json.loads(state_path.read_text(encoding="utf-8")), manifest)
    else:
        state = executor.create_state(manifest)
    settings = {entry["name"]: entry["value"] for entry in manifest["variables"]["environment_setting"]}
    domains = {entry["name"]: entry["value"] for entry in manifest["variables"]["domain_binding"]}
    env = {**{key: value for key, value in os.environ.items() if key in HOST_ENV_KEYS}, **settings, **domains,
           "ARTGENIAL_PROJECT": "artgenial_" + config["slug"].replace("-", "_"),
           "FRONTEND_HOST": config["domains"]["frontend"].split("://", 1)[1],
           "CRM_API_HOST": config["domains"]["crm_api"].split("://", 1)[1],
           "AUTH_API_HOST": config["domains"]["auth_api"].split("://", 1)[1],
           "CORE_API_HOST": config["domains"]["core_api"].split("://", 1)[1],
           "PROCESSOR_API_HOST": config["domains"]["processor_api"].split("://", 1)[1],
           "FLOW_API_HOST": config["domains"]["flow_api"].split("://", 1)[1],
           "FLOW_DATABASE": provision._commercial_database(config["slug"] + "-flow"),
           "CLICKHOUSE_DATABASE": "artgenial_flow",
           "CLICKHOUSE_USERNAME": "artgenial",
           "INSTALLATION_NAME": config["installation_name"],
           "INSTALLATION_KEY": config["installation_key"],
           "ADMIN_NAME": config["administrator"]["name"],
           "ADMIN_EMAIL": config["administrator"]["email"]}
    return manifest, state, env, runtime


def service_runtime_values(manifest, runtime):
    """Materialize only the credential names each catalog service consumes."""
    names = {item["name"] for item in manifest["infrastructure"]} - {"mailhog", "evo-frontend"}
    grants = {name: set(EXTRA_SERVICE_KEYS.get(name, ())) for name in names}
    for entry in manifest["variables"]["secret_reference"]:
        for service in entry["services"]:
            if service not in grants:
                raise InstallError("Secret catalog grants an unknown or public service")
            grants[service].add(entry["name"])
    for service in SMTP_SERVICES:
        grants[service].update(SMTP_KEYS & runtime.keys())
    result = {}
    for service, keys in grants.items():
        values = {key: runtime[key] for key in keys}
        if service == "evo-core":
            values["DB_PASSWORD"] = values.pop("POSTGRES_PASSWORD")
        if service in SMTP_SERVICES:
            redis_db = 1 if service.startswith("evo-auth") else 0
            values["REDIS_URL"] = f"redis://:{runtime['REDIS_PASSWORD']}@redis:6379/{redis_db}"
        if service.startswith("evo-crm"):
            values["EVO_AI_ENCRYPTION_KEY"] = runtime["ENCRYPTION_KEY"]
        if service == "evo-flow":
            # Auth expects the same service token that Flow already uses for CRM.
            values["EVO_AUTH_API_TOKEN"] = runtime["EVOAI_CRM_API_TOKEN"]
        result[service] = values
    return result


def write_service_env_files(directory, manifest, runtime):
    resolved = directory.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise InstallError("Service credential files must be outside the repository")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    for service, values in service_runtime_values(manifest, runtime).items():
        path = directory / f"{service}.env"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for key, value in sorted(values.items()):
                stream.write(f"{key}={value}\n")


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    if ROOT == path.resolve() or ROOT in path.resolve().parents:
        raise InstallError("Executor state must be outside the repository")
    fd, temporary = tempfile.mkstemp(prefix=".artgenial-state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def compose(env, *args):
    command = ["docker", "compose", "-f", str(COMPOSE), "--project-name", env["ARTGENIAL_PROJECT"], *args]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise InstallError("Docker Compose operation failed: " + " ".join(args[:3]))
    return completed.stdout.strip()


def prepare_shared_schema(env):
    """Use the CRM master schema once, following the existing setup sequence."""
    database = env["POSTGRES_DATABASE"]
    count = compose(env, "exec", "-T", "postgres", "psql", "-U", env["POSTGRES_USERNAME"],
                    "-d", database, "-tAc", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
    if count == "0":
        compose(env, "run", "--rm", "--no-deps", "--entrypoint", "bundle", "evo-crm",
                "exec", "rails", "db:schema:load")
    elif not count.isdigit():
        raise InstallError("Could not inspect the commercial database")
    elif compose(env, "exec", "-T", "postgres", "psql", "-U", env["POSTGRES_USERNAME"],
                 "-d", database, "-tAc", "SELECT to_regclass('public.schema_migrations') IS NOT NULL") != "t":
        raise InstallError("Existing database has no migration ledger; manual review required")
    compose(env, "run", "--rm", "--no-deps", "--entrypoint", "bundle", "evo-auth",
            "exec", "rails", "runner", "/opt/artgenial/mark_auth_migrations.rb")
    flow_db = env["FLOW_DATABASE"]
    exists = compose(env, "exec", "-T", "postgres", "psql", "-U", env["POSTGRES_USERNAME"],
                     "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{flow_db}'")
    if exists != "1":
        compose(env, "exec", "-T", "postgres", "createdb", "-U", env["POSTGRES_USERNAME"], flow_db)


def phase(state, manifest, state_path, name, action):
    current = state["phases"][name]
    if current == "completed":
        return state
    if current in ("blocked", "failed"):
        state = executor.retry_phase(state, manifest, name)
    state = executor.start_phase(state, manifest, name)
    save_state(state_path, state)
    try:
        state = action(state)
        state = executor.complete_phase(state, manifest, name)
    except Exception:
        state = executor.fail_phase(state, manifest, name)
        save_state(state_path, state)
        raise
    save_state(state_path, state)
    return state


def http_request(url, *, data=None, headers=None):
    request = Request(url, data=data, headers=headers or {})
    with urlopen(request, timeout=15) as response:
        return response.status, response.read(5_000_000), response.headers


def check(manifest, env, check_item, token):
    kind = check_item["kind"]
    target = check_item["target"]
    if kind == "public_http":
        return http_request(target)[0] == 200
    if kind == "authenticated_account":
        status, body, _ = http_request(target, headers={"Authorization": "Bearer " + token})
        payload = json.loads(body)
        return status == 200 and bool(payload.get("data", {}).get("id"))
    if kind == "frontend_binding":
        origin = manifest["public_endpoints"]["frontend"]
        _, html, _ = http_request(origin)
        assets = re.findall(rb'(?:src|href)=["\']([^"\']+\.js)["\']', html)
        if not assets:
            return False
        content = b"".join(http_request(origin + path.decode() if path.startswith(b"/") else path.decode())[1]
                           for path in assets)
        return check_item["target"].encode() in content and b"_PLACEHOLDER" not in content
    if kind == "websocket_upgrade":
        import base64
        import http.client
        import secrets
        from urllib.parse import urlsplit
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        parsed = urlsplit(target)
        connection_type = http.client.HTTPSConnection if parsed.scheme == "wss" else http.client.HTTPConnection
        connection = connection_type(parsed.hostname, parsed.port, timeout=15)
        try:
            connection.request("GET", parsed.path, headers={"Connection": "Upgrade", "Upgrade": "websocket",
                                                            "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": key})
            response = connection.getresponse()
            return response.status == 101 and response.getheader("Upgrade", "").lower() == "websocket"
        finally:
            connection.close()
    return False


def _install_prepared(manifest, state, env, runtime, state_path):
    compose(env, "config", "--quiet")

    def preparation(current):
        for name in current["evidence"]["secrets"]:
            current = executor.attest_secret(current, manifest, name)
            save_state(state_path, current)
        return current

    state = phase(state, manifest, state_path, "PREPARACAO", preparation)

    def infrastructure(current):
        compose(env, "build")
        compose(env, "up", "-d", "--wait", "postgres", "redis", "rabbitmq", "clickhouse")
        prepare_shared_schema(env)
        for name in ("postgres", "redis", "rabbitmq", "clickhouse"):
            current = executor.attest_service(current, manifest, name)
            save_state(state_path, current)
        compose(env, "up", "-d", "--wait", "evo-auth", "evo-crm", "evo-core", "evo-processor", "evo-bot-runtime", "evo-flow", "evo-frontend", "evo-auth-sidekiq", "evo-crm-sidekiq", "ingress")
        for name in current["evidence"]["services"]:
            current = executor.attest_service(current, manifest, name)
            save_state(state_path, current)
        verify_smtp(runtime)
        current = executor.attest_commercial_email(current, manifest)
        return current

    state = phase(state, manifest, state_path, "INFRAESTRUTURA", infrastructure)

    def initialization(current):
        compose(env, "exec", "-T", "evo-crm", "bundle", "exec", "rails", "db:migrate")
        compose(env, "exec", "-T", "evo-auth", "bundle", "exec", "rails", "db:migrate")
        compose(env, "exec", "-T", "evo-processor", "alembic", "upgrade", "head")
        compose(env, "exec", "-T", "evo-flow", "node_modules/.bin/typeorm", "migration:run", "-d", "dist/database/ormconfig.js")
        current = executor.attest_initialization(current, manifest, "migrations")
        save_state(state_path, current)
        # The Auth bootstrap checks RuntimeConfig.account and administrator independently.
        # Password stays only in this process and the target container environment.
        password = getpass.getpass("Initial administrator password: ")
        if not password:
            raise InstallError("Administrator password is required")
        auth_env = {**env, "ADMIN_PASSWORD": password}
        compose(auth_env, "exec", "-T", "-e", "ADMIN_PASSWORD", "-e", "INSTALLATION_NAME",
                "-e", "FRONTEND_HOST", "-e", "ADMIN_EMAIL", "-e", "ADMIN_NAME",
                "evo-auth", "bundle", "exec", "rails", "runner", "/opt/artgenial/bootstrap_auth.rb")
        for step in ("auth_account", "initial_administrator"):
            current = executor.attest_initialization(current, manifest, step)
            save_state(state_path, current)
        compose(env, "exec", "-T", "-e", "INSTALLATION_KEY", "-e", "ADMIN_EMAIL",
                "evo-crm", "bundle", "exec", "rails", "runner", "/opt/artgenial/bootstrap_base.rb")
        current = executor.attest_initialization(current, manifest, "artgenial_base")
        return current

    state = phase(state, manifest, state_path, "INICIALIZACAO", initialization)

    def validation(current):
        password = getpass.getpass("Administrator password for validation: ")
        login_url = manifest["public_endpoints"]["auth_api"] + "/api/v1/auth/login"
        body = json.dumps({"email": env["ADMIN_EMAIL"], "password": password}).encode()
        _, login_body, _ = http_request(login_url, data=body, headers={"Content-Type": "application/json"})
        token = json.loads(login_body).get("data", {}).get("token", {}).get("access_token")
        if not token:
            raise InstallError("Administrator login validation failed")
        failed = []
        for item in manifest["validation"]:
            try:
                passed = check(manifest, env, item, token)
            except (HTTPError, URLError, ValueError, KeyError):
                passed = False
            current = executor.record_check(current, manifest, item["id"], passed)
            save_state(state_path, current)
            if not passed and item["required"]:
                failed.append(item["id"])
        if failed:
            raise InstallError("Mandatory checks failed: " + ", ".join(failed))
        return current

    state = phase(state, manifest, state_path, "VALIDACAO", validation)
    state = executor.complete_delivery(state, manifest)
    save_state(state_path, state)
    print("Commercial installation validated; executor delivery ready")


def install(config_path, runtime_path, state_path):
    if shutil.which("docker") is None:
        raise InstallError("Docker Compose is unavailable")
    manifest, state, env, runtime = prepare(config_path, runtime_path, state_path)
    with tempfile.TemporaryDirectory(prefix="artgenial-service-env-") as temporary:
        directory = Path(temporary)
        write_service_env_files(directory, manifest, runtime)
        env["ARTGENIAL_SERVICE_ENV_DIR"] = directory.as_posix()
        _install_prepared(manifest, state, env, runtime, state_path)


def main():
    parser = argparse.ArgumentParser(description="ArtGenial commercial Docker Compose installation")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runtime-env", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        install(args.config, args.runtime_env, args.state)
    except (InstallError, executor.ExecutorError, provision.ConfigurationError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Installation stopped: unexpected operation failure; inspect the isolated deployment", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
