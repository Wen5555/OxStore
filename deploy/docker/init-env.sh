#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -e .env ]; then printf '%s\n' '.env already exists; preserved.'; exit 0; fi
command -v openssl >/dev/null
umask 077
{
  printf '%s\n' 'OXSTORE_VERSION=0.1.0-docker.1' 'COMPOSE_PROJECT_NAME=oxstore' 'APP_BIND_ADDRESS=127.0.0.1' 'APP_PORT=8088'
  printf 'DB_PASSWORD=%s\n' "$(openssl rand -hex 32)"
  printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)"
  printf 'TOKEN_LOOKUP_KEY=%s\n' "$(openssl rand -hex 32)"
  printf 'ADMIN_INITIAL_PASSWORD=Ox!%s\n' "$(openssl rand -hex 32)"
  printf '%s\n' 'HISTORY_COMPLETE_SINCE='
} > .env
printf '%s\n' 'Created .env. Username: admin. Read initial password locally from .env.'
