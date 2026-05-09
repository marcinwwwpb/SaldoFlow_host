#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

USE_DAEMON=1
SEED_SHOWCASE=1
FORCE_SEED_REBUILD=0
BOOTSTRAP_ADMIN=1
USE_SQLITE=0
ADDRPORT="127.0.0.1:8000"
FORCE_REINSTALL=0
SERVER_EXTRA_ARGS=()
APP_DISPLAY_NAME="SaldoFlow"
ORACLE_MODE="docker"
ORACLE_HOST="${ORACLE_HOST:-127.0.0.1}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
ORACLE_SERVICE_NAME="${ORACLE_SERVICE_NAME:-FREEPDB1}"
ORACLE_USER="${ORACLE_USER:-SALDOFLOW_APP}"
ORACLE_PASSWORD="${ORACLE_PASSWORD:-change-me}"
ORACLE_DSN="${ORACLE_DSN:-}"

print_help() {
  cat <<'EOH'
Uruchamia Oracle, Django i opcjonalnie demona importu.
Domyślnie przygotowuje również duży zestaw danych pokazowych.

Użycie:
  ./scripts/start_demo_linux.sh [opcje]

Opcje:
  --skip-daemon              Nie uruchamiaj demona importu.
  --skip-seed                Nie ładuj dużego zestawu danych pokazowych.
  --rebuild-seed             Usuń i odbuduj duży zestaw danych pokazowych.
  --no-bootstrap             Nie twórz/nie aktualizuj kont marcin/test.
  --oracle                   Użyj Oracle (domyślnie).
  --sqlite                   Użyj SQLite zamiast Oracle i pomiń Docker.
  --oracle-docker            Oracle z kontenera Docker/Compose.
  --oracle-external          Oracle zewnętrzne — bez uruchamiania Dockera.
  --oracle-host HOST         Host Oracle.
  --oracle-port PORT         Port Oracle.
  --oracle-service NAME      Service name / PDB, np. FREEPDB1.
  --oracle-user USER         Użytkownik schematu aplikacji.
  --oracle-password PASS     Hasło użytkownika schematu aplikacji.
  --oracle-dsn DSN           Gotowy DSN, np. host:1521/FREEPDB1.
  --addr HOST:PORT           Adres dla runserver (domyślnie 127.0.0.1:8000).
  --noreload                 Wyłącz autoreloader Django (zalecane przy starcie w tle).
  --reinstall                Wymuś ponowną instalację zależności pip.
  -h, --help                 Pokaż pomoc.

Zmienne środowiskowe Oracle:
  ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE_NAME, ORACLE_USER,
  ORACLE_PASSWORD, ORACLE_DSN
EOH
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-daemon) USE_DAEMON=0 ;;
    --skip-seed) SEED_SHOWCASE=0 ;;
    --rebuild-seed) SEED_SHOWCASE=1; FORCE_SEED_REBUILD=1 ;;
    --no-bootstrap) BOOTSTRAP_ADMIN=0 ;;
    --oracle) USE_SQLITE=0 ;;
    --sqlite) USE_SQLITE=1 ;;
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
    --addr)
      shift
      ADDRPORT="${1:-}"
      [[ -n "$ADDRPORT" ]] || { echo "Brak wartości dla --addr" >&2; exit 1; }
      ;;
    --noreload) SERVER_EXTRA_ARGS+=("--noreload") ;;
    --reinstall) FORCE_REINSTALL=1 ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "Nieznana opcja: $1" >&2; print_help; exit 1 ;;
  esac
  shift
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Brak wymaganego polecenia: $1" >&2; exit 1; }
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Nie znaleziono docker compose ani docker-compose." >&2
    exit 1
  fi
}

wait_for_oracle() {
  local name="saldoflow-oracle"
  local status=""
  echo "[INFO] Czekam aż Oracle będzie gotowe..."
  for _ in $(seq 1 120); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || true)"
    case "$status" in
      healthy|running)
        echo "[OK] Oracle gotowe (${status})."
        return 0
        ;;
    esac
    sleep 5
  done
  echo "[ERROR] Oracle nie osiągnęło stanu healthy/running." >&2
  docker logs "$name" --tail 80 || true
  exit 1
}

prepare_oracle_docker() {
  require_cmd docker
  if docker inspect saldoflow-oracle >/dev/null 2>&1; then
    local image
    image="$(docker inspect --format '{{.Config.Image}}' saldoflow-oracle 2>/dev/null || true)"
    if [[ "$image" != *"oracle-free"* ]]; then
      echo "[ERROR] Kontener saldoflow-oracle istnieje, ale nie wygląda na Oracle Free: $image" >&2
      echo "Usuń go ręcznie lub zmień nazwę kontenera." >&2
      exit 1
    fi
    echo "[INFO] Używam istniejącego kontenera saldoflow-oracle."
    docker start saldoflow-oracle >/dev/null 2>&1 || true
  else
    echo "[INFO] Uruchamiam Oracle przez compose.oracle.yml"
    compose_cmd -f compose.oracle.yml up -d
  fi
  wait_for_oracle
}

prepare_python() {
  require_cmd python3
  if [[ -d .venv && ! -x .venv/bin/python3 ]]; then
    echo "[WARN] Wykryto uszkodzone środowisko .venv — odtwarzam je od zera."
    rm -rf .venv
  fi
  if [[ ! -d .venv ]]; then
    echo "[INFO] Tworzę virtualenv .venv"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python3 -m pip install --upgrade pip >/dev/null

  local deps_ready=0
  if python3 - <<'PYDEP' >/dev/null 2>&1
import importlib.util
mods = ['django', 'openpyxl', 'oracledb', 'psycopg']
raise SystemExit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)
PYDEP
  then
    deps_ready=1
  fi

  if [[ "$FORCE_REINSTALL" -eq 1 || ! -f .venv/.deps_installed || "$deps_ready" -ne 1 ]]; then
    echo "[INFO] Instaluję zależności Python"
    pip install -r requirements.txt
    touch .venv/.deps_installed
  fi
  export PYTHON_BIN="$(command -v python3)"
}

prepare_runtime() {
  mkdir -p \
    runtime/watch/dom \
    runtime/watch/firma \
    runtime/daemon_status \
    runtime/emails \
    runtime/archive/dom/ok \
    runtime/archive/dom/error \
    runtime/archive/firma/ok \
    runtime/archive/firma/error \
    runtime/logs \
    runtime/launcher
}

prepare_daemon() {
  [[ "$USE_DAEMON" -eq 1 ]] || return 0
  require_cmd make
  require_cmd gcc
  if [[ ! -f demon/import_watchd || demon/import_watchd.c -nt demon/import_watchd ]]; then
    echo "[INFO] Kompiluję demona importu"
    (cd demon && make)
  fi
}

export_common_env() {
  export APP_NAME="$APP_DISPLAY_NAME"
  export DJANGO_DEBUG=1
  export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,testserver"
  export DJANGO_CSRF_TRUSTED_ORIGINS="http://127.0.0.1,http://localhost"
  export EMAIL_FILE_PATH="$PROJECT_DIR/runtime/emails"
  export DEMON_STATUS_DIR="runtime/daemon_status"
}

export_oracle_env() {
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
}

run_bootstrap() {
  if [[ "$BOOTSTRAP_ADMIN" -eq 1 ]]; then
    echo "[INFO] Tworzę/aktualizuję konta pokazowe marcin/test"
    python3 manage.py bootstrap_demo_security
  fi
  if [[ "$SEED_SHOWCASE" -eq 1 ]]; then
    echo "[INFO] Przygotowuję duży zestaw danych demonstracyjnych"
    if [[ "$FORCE_SEED_REBUILD" -eq 1 ]]; then
      python3 manage.py seed_showcase_data --force
    else
      python3 manage.py seed_showcase_data
    fi
  fi
}

run_oracle_flow() {
  export_oracle_env
  if [[ "$ORACLE_MODE" == "docker" ]]; then
    prepare_oracle_docker
  else
    echo "[INFO] Tryb Oracle external — pomijam uruchamianie Dockera."
    echo "[INFO] DSN: ${ORACLE_DSN} | USER: ${ORACLE_USER}"
  fi

  prepare_python
  prepare_runtime
  prepare_daemon
  export_common_env

  echo "[INFO] Wykonuję migracje"
  python3 manage.py migrate
  run_bootstrap

  echo
  echo "[OK] Aplikacja będzie dostępna pod: http://${ADDRPORT}"
  echo "[OK] Nazwa projektu w interfejsie: ${APP_DISPLAY_NAME}"
  echo "[OK] Panel admina aplikacji: http://${ADDRPORT}/panel-admina/"
  echo "[OK] Django admin: http://${ADDRPORT}/admin/"
  echo "[OK] Superadmin: marcin / danzel12"
  echo "[OK] Księgowy: ksiegowy / ksiegowy123"
  echo "[OK] Audytor: audytor / audytor123"
  echo "[OK] Konto testowe: test / test"
  echo "[OK] Baza Oracle: ${ORACLE_DSN} (${ORACLE_USER})"
  echo "[OK] Dane demona: runtime/watch/*, runtime/archive/*, runtime/daemon_status"
  if [[ "$USE_DAEMON" -eq 1 ]]; then
    exec python3 manage.py runserver_with_daemon \
      --module dom \
      --module firma \
      --dom-watchdir "$PROJECT_DIR/runtime/watch/dom" \
      --firma-watchdir "$PROJECT_DIR/runtime/watch/firma" \
      --status-dir "$PROJECT_DIR/runtime/daemon_status" \
      --archive-dir "$PROJECT_DIR/runtime/archive" \
      "$ADDRPORT" \
      "${SERVER_EXTRA_ARGS[@]}"
  else
    echo "[OK] Demon wyłączony (--skip-daemon)."
    exec python3 manage.py runserver "$ADDRPORT" "${SERVER_EXTRA_ARGS[@]}"
  fi
}

run_sqlite_flow() {
  export DB_ENGINE=sqlite
  USE_DAEMON=0
  prepare_python
  prepare_runtime
  export_common_env

  echo "[INFO] Wykonuję migracje SQLite"
  python3 manage.py migrate
  run_bootstrap

  echo
  echo "[OK] Aplikacja będzie dostępna pod: http://${ADDRPORT}"
  echo "[OK] Nazwa projektu w interfejsie: ${APP_DISPLAY_NAME}"
  echo "[OK] Superadmin: marcin / danzel12"
  echo "[OK] Księgowy: ksiegowy / ksiegowy123"
  echo "[OK] Audytor: audytor / audytor123"
  echo "[OK] Konto testowe: test / test"
  echo "[OK] Tryb SQLite. Demon jest wyłączony automatycznie."
  exec python3 manage.py runserver "$ADDRPORT" "${SERVER_EXTRA_ARGS[@]}"
}

if [[ "$USE_SQLITE" -eq 1 ]]; then
  run_sqlite_flow
else
  run_oracle_flow
fi
