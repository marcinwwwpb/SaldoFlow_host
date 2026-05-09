#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

USE_SQLITE=1
FORCE=0
REINSTALL=0
ORACLE_MODE="docker"
ORACLE_HOST="${ORACLE_HOST:-127.0.0.1}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
ORACLE_SERVICE_NAME="${ORACLE_SERVICE_NAME:-FREEPDB1}"
ORACLE_USER="${ORACLE_USER:-SALDOFLOW_APP}"
ORACLE_PASSWORD="${ORACLE_PASSWORD:-change-me}"
ORACLE_DSN="${ORACLE_DSN:-}"

usage() {
  cat <<'EOH'
Przygotowuje realistyczne dane testowe dla SaldoFlow.

Użycie:
  ./seed_test_data_linux.sh [--oracle|--sqlite] [--force] [--reinstall] [opcje Oracle]

Opcje:
  --sqlite            Użyj SQLite (domyślnie)
  --oracle            Użyj Oracle
  --oracle-docker     Oracle z kontenera Docker/Compose
  --oracle-external   Oracle zewnętrzne — bez uruchamiania Dockera
  --oracle-host HOST  Host Oracle
  --oracle-port PORT  Port Oracle
  --oracle-service    Service name / PDB, np. FREEPDB1
  --oracle-user USER  Użytkownik schematu aplikacji
  --oracle-password   Hasło użytkownika schematu aplikacji
  --oracle-dsn DSN    Gotowy DSN, np. host:1521/FREEPDB1
  --force             Usuń i odbuduj dane demonstracyjne
  --reinstall         Wymuś ponowną instalację zależności pip
EOH
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Brakuje docker compose / docker-compose" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sqlite) USE_SQLITE=1 ;;
    --oracle) USE_SQLITE=0 ;;
    --oracle-docker) USE_SQLITE=0; ORACLE_MODE="docker" ;;
    --oracle-external) USE_SQLITE=0; ORACLE_MODE="external" ;;
    --oracle-host)
      shift; ORACLE_HOST="${1:-}"; [[ -n "$ORACLE_HOST" ]] || { echo "Brak wartości dla --oracle-host" >&2; exit 1; }
      ;;
    --oracle-port)
      shift; ORACLE_PORT="${1:-}"; [[ -n "$ORACLE_PORT" ]] || { echo "Brak wartości dla --oracle-port" >&2; exit 1; }
      ;;
    --oracle-service)
      shift; ORACLE_SERVICE_NAME="${1:-}"; [[ -n "$ORACLE_SERVICE_NAME" ]] || { echo "Brak wartości dla --oracle-service" >&2; exit 1; }
      ;;
    --oracle-user)
      shift; ORACLE_USER="${1:-}"; [[ -n "$ORACLE_USER" ]] || { echo "Brak wartości dla --oracle-user" >&2; exit 1; }
      ;;
    --oracle-password)
      shift; ORACLE_PASSWORD="${1:-}"; [[ -n "$ORACLE_PASSWORD" ]] || { echo "Brak wartości dla --oracle-password" >&2; exit 1; }
      ;;
    --oracle-dsn)
      shift; ORACLE_DSN="${1:-}"; [[ -n "$ORACLE_DSN" ]] || { echo "Brak wartości dla --oracle-dsn" >&2; exit 1; }
      ;;
    --force) FORCE=1 ;;
    --reinstall) REINSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Nieznana opcja: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [[ -d .venv && ! -x .venv/bin/python ]]; then
  rm -rf .venv
fi
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null

deps_ready=0
if python - <<'PYDEP' >/dev/null 2>&1
import importlib.util
mods = ['django', 'openpyxl', 'oracledb', 'psycopg']
raise SystemExit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)
PYDEP
then
  deps_ready=1
fi

if [[ "$REINSTALL" -eq 1 || ! -f .venv/.deps_installed || "$deps_ready" -ne 1 ]]; then
  pip install -r requirements.txt
  touch .venv/.deps_installed
fi

mkdir -p runtime/watch/dom runtime/watch/firma runtime/daemon_status runtime/emails runtime/archive/dom/ok runtime/archive/dom/error runtime/archive/firma/ok runtime/archive/firma/error runtime/logs runtime/launcher
export APP_NAME="SaldoFlow"
export DJANGO_DEBUG=1
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,testserver"
export DJANGO_CSRF_TRUSTED_ORIGINS="http://127.0.0.1,http://localhost"
export EMAIL_FILE_PATH="$PROJECT_DIR/runtime/emails"
export DEMON_STATUS_DIR="runtime/daemon_status"

if [[ "$USE_SQLITE" -eq 1 ]]; then
  export DB_ENGINE=sqlite
else
  export DB_ENGINE=oracle
  export ORACLE_HOST="$ORACLE_HOST"
  export ORACLE_PORT="$ORACLE_PORT"
  export ORACLE_SERVICE_NAME="$ORACLE_SERVICE_NAME"
  export ORACLE_USER="$ORACLE_USER"
  export ORACLE_PASSWORD="$ORACLE_PASSWORD"
  if [[ -n "$ORACLE_DSN" ]]; then
    export ORACLE_DSN="$ORACLE_DSN"
  else
    export ORACLE_DSN="${ORACLE_HOST}:${ORACLE_PORT}/${ORACLE_SERVICE_NAME}"
  fi

  if [[ "$ORACLE_MODE" == "docker" ]]; then
    if command -v docker >/dev/null 2>&1; then
      if docker inspect saldoflow-oracle >/dev/null 2>&1; then
        docker start saldoflow-oracle >/dev/null 2>&1 || true
      else
        compose_cmd -f compose.oracle.yml up -d
      fi
    else
      echo "Brakuje docker. Użyj --oracle-external albo zainstaluj Docker." >&2
      exit 1
    fi
  else
    echo "[INFO] Tryb Oracle external — pomijam uruchamianie Dockera."
    echo "[INFO] DSN: ${ORACLE_DSN} | USER: ${ORACLE_USER}"
  fi
fi

python manage.py migrate
python manage.py bootstrap_demo_security
if [[ "$FORCE" -eq 1 ]]; then
  python manage.py seed_showcase_data --force
else
  python manage.py seed_showcase_data
fi
