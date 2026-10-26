#!/bin/sh
set -eu
export REDIS_URL="redis://:${REDIS_PASSWORD:?}@redis:6379"
exec "$@"
