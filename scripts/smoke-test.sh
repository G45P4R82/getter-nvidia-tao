#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${TAO_BASE_URL:-http://localhost:${NGINX_HTTP_PORT:-8090}}"

printf 'Checking TAO FTMS at %s\n' "$BASE_URL"
status_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$BASE_URL")"

case "$status_code" in
  2*|3*|401|403)
    printf 'TAO endpoint reachable (HTTP %s).\n' "$status_code"
    ;;
  *)
    printf 'TAO endpoint is not healthy (HTTP %s).\n' "$status_code" >&2
    exit 1
    ;;
esac

if command -v docker >/dev/null 2>&1; then
  docker ps --format '{{.Names}}' | grep -Eq 'tao_api_app|nginx' || {
    printf 'Expected TAO API containers are not running.\n' >&2
    exit 1
  }
fi
