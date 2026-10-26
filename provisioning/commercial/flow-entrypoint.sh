#!/bin/sh
set -eu
export POSTGRES_DB_PASSWORD="${POSTGRES_PASSWORD:?}"
export RABBITMQ_URL="amqp://${RABBITMQ_DEFAULT_USER:?}:${RABBITMQ_DEFAULT_PASS:?}@rabbitmq:5672"
node_modules/.bin/typeorm migration:run -d dist/database/ormconfig.js
exec node dist/main.js
