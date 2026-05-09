#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

usage() {
  cat <<'EOH'
Uruchamia pełny stos Oracle dla SaldoFlow: baza, aplikacja, demon i bootstrap bezpieczeństwa.

Użycie:
  ./run_all_oracle_linux.sh start [opcje Oracle]
  ./run_all_oracle_linux.sh stop [--volumes]
  ./run_all_oracle_linux.sh restart [opcje Oracle]
  ./run_all_oracle_linux.sh status
  ./run_all_oracle_linux.sh logs
EOH
}

start_stack() {
  echo "[INFO] Startuję aplikację na Oracle..."
  "$PROJECT_DIR/launcher_linux.sh" start --oracle-docker "$@"
  echo "[INFO] Stosuję skrypty bezpieczeństwa Oracle..."
  "$PROJECT_DIR/bootstrap_oracle_security.sh" --oracle-docker "$@"
  echo "[OK] Pełny stos Oracle został uruchomiony."
}

stop_stack() {
  "$PROJECT_DIR/launcher_linux.sh" stop "$@"
}

restart_stack() {
  "$PROJECT_DIR/launcher_linux.sh" stop
  start_stack "$@"
}

case "${1:-}" in
  start)
    shift
    if [[ " ${*:-} " == *" --oracle-external "* ]]; then
      "$PROJECT_DIR/launcher_linux.sh" start "$@"
      "$PROJECT_DIR/bootstrap_oracle_security.sh" "$@"
    else
      start_stack "$@"
    fi
    ;;
  stop)
    shift
    stop_stack "$@"
    ;;
  restart)
    shift
    if [[ " ${*:-} " == *" --oracle-external "* ]]; then
      "$PROJECT_DIR/launcher_linux.sh" stop
      "$PROJECT_DIR/launcher_linux.sh" start "$@"
      "$PROJECT_DIR/bootstrap_oracle_security.sh" "$@"
    else
      restart_stack "$@"
    fi
    ;;
  status)
    "$PROJECT_DIR/launcher_linux.sh" status
    ;;
  logs)
    "$PROJECT_DIR/launcher_linux.sh" logs
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    echo "Nieznana komenda: $1" >&2
    usage
    exit 1
    ;;
esac
