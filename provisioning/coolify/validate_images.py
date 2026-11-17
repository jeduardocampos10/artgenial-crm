#!/usr/bin/env python3
"""Fail closed unless every homologation application image is immutable."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

IMAGE_VARIABLES = (
    "AUTH_IMAGE",
    "CRM_IMAGE",
    "FRONTEND_IMAGE",
    "CORE_IMAGE",
    "PROCESSOR_IMAGE",
    "BOT_RUNTIME_IMAGE",
    "EVOLUTION_API_IMAGE",
    "FLOW_IMAGE",
)

# A digest is content-addressed. A full 40-character commit tag is accepted for
# CI outputs because workflows publish exactly github.sha and never publish on PRs.
IMMUTABLE_REF = re.compile(
    r"^ghcr\.io/jeduardocampos10/artgenial-hml-[a-z0-9-]+"
    r"(?::[0-9a-f]{40}|@sha256:[0-9a-f]{64})$"
)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(values: dict[str, str]) -> list[str]:
    errors = []
    for variable in IMAGE_VARIABLES:
        value = values.get(variable, "")
        if not IMMUTABLE_REF.fullmatch(value):
            errors.append(
                f"{variable} must be a GHCR sha256 digest or a full 40-character commit tag"
            )
    return errors


def main(argv: list[str]) -> int:
    values = dict(os.environ)
    if len(argv) == 2:
        values.update(read_env(Path(argv[1])))
    elif len(argv) > 2:
        print(f"usage: {argv[0]} [coolify.env]", file=sys.stderr)
        return 2

    errors = validate(values)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("All homologation application images are immutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
