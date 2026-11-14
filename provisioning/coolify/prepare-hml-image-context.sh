#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 COMPONENT CONTEXT" >&2
  exit 2
fi

component="$1"
context="$2"
root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
test -f "$context/Dockerfile"
cp "$context/Dockerfile" "$context/Dockerfile.hml"
mkdir -p "$context/.artgenial"

case "$component" in
  auth)
    install -m 0444 "$root/provisioning/commercial/mark_auth_migrations.rb" "$context/.artgenial/mark_auth_migrations.rb"
    install -m 0444 "$root/provisioning/commercial/bootstrap_auth.rb" "$context/.artgenial/bootstrap_auth.rb"
    cat >>"$context/Dockerfile.hml" <<'EOF'

USER root
COPY --chown=1000:1000 .artgenial/ /opt/artgenial/
RUN test -f /opt/artgenial/mark_auth_migrations.rb \
 && test -f /opt/artgenial/bootstrap_auth.rb \
 && chmod 0444 /opt/artgenial/*.rb
USER rails:rails
EOF
    ;;
  bot-runtime)
    install -m 0555 "$root/provisioning/commercial/bot-entrypoint.sh" "$context/.artgenial/bot-entrypoint.sh"
    cat >>"$context/Dockerfile.hml" <<'EOF'

COPY .artgenial/bot-entrypoint.sh /opt/artgenial/bot-entrypoint.sh
RUN test -x /opt/artgenial/bot-entrypoint.sh
EOF
    ;;
  flow)
    install -m 0555 "$root/provisioning/commercial/flow-entrypoint.sh" "$context/.artgenial/flow-entrypoint.sh"
    cat >>"$context/Dockerfile.hml" <<'EOF'

USER root
COPY --chown=nestjs:nodejs .artgenial/flow-entrypoint.sh /opt/artgenial/flow-entrypoint.sh
RUN test -x /opt/artgenial/flow-entrypoint.sh
USER nestjs
EOF
    ;;
  evolution-api)
    rmdir "$context/.artgenial"
    ;;
  *)
    echo "unsupported homologation component: $component" >&2
    exit 2
    ;;
esac

test -f "$context/Dockerfile.hml"
