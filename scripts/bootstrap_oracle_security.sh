#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

ORACLE_MODE="docker"
ORACLE_HOST="${ORACLE_HOST:-127.0.0.1}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
ORACLE_SERVICE_NAME="${ORACLE_SERVICE_NAME:-FREEPDB1}"
ORACLE_USER="${ORACLE_USER:-SALDOFLOW_APP}"
ORACLE_PASSWORD="${ORACLE_PASSWORD:-change-me}"
ORACLE_DSN="${ORACLE_DSN:-}"
ORACLE_ADMIN_USER="${ORACLE_ADMIN_USER:-SYSTEM}"
ORACLE_ADMIN_PASSWORD="${ORACLE_ADMIN_PASSWORD:-oracle}"
CONTAINER_NAME="${ORACLE_CONTAINER_NAME:-saldoflow-oracle}"

usage() {
  cat <<'EOH'
Stosuje skrypty bezpieczeństwa Oracle dla projektu SaldoFlow.

Użycie:
  ./bootstrap_oracle_security.sh [--oracle-docker|--oracle-external] [opcje]

Opcje:
  --oracle-docker            Oracle w kontenerze Docker (domyślnie)
  --oracle-external          Oracle zewnętrzne
  --oracle-host HOST         Host Oracle
  --oracle-port PORT         Port Oracle
  --oracle-service NAME      Service name / PDB
  --oracle-user USER         Użytkownik schematu aplikacji
  --oracle-password PASS     Hasło użytkownika schematu aplikacji
  --oracle-dsn DSN           Gotowy DSN, np. host:1521/FREEPDB1
  --admin-user USER          Administrator Oracle do uruchomienia 00_users_roles.sql
  --admin-password PASS      Hasło administratora Oracle
  -h, --help                 Pokaż pomoc
EOH
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --oracle-docker) ORACLE_MODE="docker" ;;
    --oracle-external) ORACLE_MODE="external" ;;
    --oracle-host) shift; ORACLE_HOST="${1:-}" ;;
    --oracle-port) shift; ORACLE_PORT="${1:-}" ;;
    --oracle-service) shift; ORACLE_SERVICE_NAME="${1:-}" ;;
    --oracle-user) shift; ORACLE_USER="${1:-}" ;;
    --oracle-password) shift; ORACLE_PASSWORD="${1:-}" ;;
    --oracle-dsn) shift; ORACLE_DSN="${1:-}" ;;
    --admin-user) shift; ORACLE_ADMIN_USER="${1:-}" ;;
    --admin-password) shift; ORACLE_ADMIN_PASSWORD="${1:-}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Nieznana opcja: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [[ -z "$ORACLE_DSN" ]]; then
  ORACLE_DSN="${ORACLE_HOST}:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
fi

run_sqlplus_host() {
  local connect="$1"
  local sql_file="$2"
  sqlplus -s "$connect" @"$sql_file"
}

run_sqlplus_docker() {
  local connect="$1"
  local sql_file="$2"
  docker exec -i "$CONTAINER_NAME" bash -lc "sqlplus -s '$connect'" < "$sql_file"
}

wait_for_docker_oracle() {
  for _ in $(seq 1 120); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER_NAME" 2>/dev/null || true)"
    case "$status" in
      healthy|running) return 0 ;;
    esac
    sleep 2
  done
  echo "[ERROR] Oracle nie osiągnęło stanu healthy/running." >&2
  return 1
}

run_sql() {
  local connect="$1"
  local sql_file="$2"
  echo "[INFO] Wykonuję $(basename "$sql_file")"
  if [[ "$ORACLE_MODE" == "docker" ]]; then
    run_sqlplus_docker "$connect" "$sql_file"
  else
    if ! command -v sqlplus >/dev/null 2>&1; then
      echo "[ERROR] W trybie external wymagany jest sqlplus w systemie." >&2
      exit 1
    fi
    run_sqlplus_host "$connect" "$sql_file"
  fi
}

if [[ "$ORACLE_MODE" == "docker" ]]; then
  command -v docker >/dev/null 2>&1 || { echo "[ERROR] Brakuje docker." >&2; exit 1; }
  docker inspect "$CONTAINER_NAME" >/dev/null 2>&1 || { echo "[ERROR] Nie znaleziono kontenera $CONTAINER_NAME." >&2; exit 1; }
  wait_for_docker_oracle
  ADMIN_CONNECT="${ORACLE_ADMIN_USER}/${ORACLE_ADMIN_PASSWORD}@//localhost:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
  APP_CONNECT="${ORACLE_USER}/${ORACLE_PASSWORD}@//localhost:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
else
  ADMIN_CONNECT="${ORACLE_ADMIN_USER}/${ORACLE_ADMIN_PASSWORD}@//${ORACLE_HOST}:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
  APP_CONNECT="${ORACLE_USER}/${ORACLE_PASSWORD}@//${ORACLE_HOST}:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
fi

run_sql "$ADMIN_CONNECT" "$PROJECT_DIR/database/oracle/00_users_roles.sql"
for sql in \
  "$PROJECT_DIR/database/oracle/10_security_context.sql" \
  "$PROJECT_DIR/database/oracle/20_audit_table.sql" \
  "$PROJECT_DIR/database/oracle/30_vpd_policy.sql" \
  "$PROJECT_DIR/database/oracle/40_key_ops_metrics.sql" \
  "$PROJECT_DIR/database/oracle/50_trigger_examples.sql" \
  "$PROJECT_DIR/database/oracle/60_business_logic.sql"; do
  run_sql "$APP_CONNECT" "$sql"
done

echo "[OK] Zastosowano skrypty Oracle dla SaldoFlow."
