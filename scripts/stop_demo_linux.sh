#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
REMOVE_VOLUMES=0
if [[ "${1:-}" == "--volumes" ]]; then
  REMOVE_VOLUMES=1
fi
if docker inspect saldoflow-oracle >/dev/null 2>&1; then
  if [[ "$REMOVE_VOLUMES" -eq 1 ]]; then
    if docker compose version >/dev/null 2>&1; then
      docker compose -f compose.oracle.yml down -v
    elif command -v docker-compose >/dev/null 2>&1; then
      docker-compose -f compose.oracle.yml down -v
    else
      docker rm -f saldoflow-oracle
    fi
  else
    docker stop saldoflow-oracle >/dev/null 2>&1 || true
    echo "[OK] Zatrzymano Oracle."
  fi
else
  echo "[INFO] Kontener saldoflow-oracle nie istnieje."
fi
