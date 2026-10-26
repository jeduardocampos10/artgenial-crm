#!/bin/sh
set -eu
export POSTGRES_CONNECTION_STRING="postgresql://${POSTGRES_USERNAME:?}:${POSTGRES_PASSWORD:?}@postgres:5432/${POSTGRES_DATABASE:?}"
exec "$@"
