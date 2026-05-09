#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PID_FILE="$PROJECT_DIR/runtime/launcher/server.pid"
LOG_FILE="$PROJECT_DIR/runtime/logs/server.log"
ADDR_FILE="$PROJECT_DIR/runtime/launcher/addrport"
ADDRPORT="127.0.0.1:8000"
PROBE_PATH="/konto/logowanie/"

usage() {
  cat <<'EOH'
Launcher dla Linux uruchamiający bazę, serwer Django i demony importu.

Użycie:
  ./launcher_linux.sh start [opcje przekazywane do start_demo_linux.sh]
  ./launcher_linux.sh stop [--volumes]
  ./launcher_linux.sh restart [opcje przekazywane do start_demo_linux.sh]
  ./launcher_linux.sh status
  ./launcher_linux.sh logs
EOH
}

extract_addr() {
  local args=("$@")
  for ((i=0; i<${#args[@]}; i++)); do
    if [[ "${args[$i]}" == "--addr" && $((i+1)) -lt ${#args[@]} ]]; then
      ADDRPORT="${args[$((i+1))]}"
      return 0
    fi
  done
}

load_addr() {
  if [[ -f "$ADDR_FILE" ]]; then
    ADDRPORT="$(cat "$ADDR_FILE")"
  fi
}

ensure_runtime() {
  mkdir -p runtime/launcher runtime/logs runtime/daemon_status
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE")"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

probe_http() {
  python3 - "$ADDRPORT" "$PROBE_PATH" <<'PY'
import sys
import urllib.request

addr, path = sys.argv[1:3]
url = f"http://{addr}{path}"
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
PY
}

show_daemon_status() {
  find runtime/daemon_status -maxdepth 1 -type f -name 'import_watchd_*.json' -print 2>/dev/null | sort | while read -r file; do
    if python3 - "$PROJECT_DIR" "$file" <<'PY'
import json
import pathlib
import sys
project_dir = pathlib.Path(sys.argv[1]).resolve()
status_path = pathlib.Path(sys.argv[2]).resolve()
expected_watch_prefix = str(project_dir / 'runtime' / 'watch')
try:
    payload = json.loads(status_path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(1)
recorded_status_file = payload.get('status_file')
watch_dir = payload.get('watch_dir', '')
if recorded_status_file:
    try:
        if pathlib.Path(recorded_status_file).resolve() == status_path:
            raise SystemExit(0)
    except Exception:
        pass
if isinstance(watch_dir, str) and watch_dir.startswith(expected_watch_prefix):
    raise SystemExit(0)
raise SystemExit(1)
PY
    then
      echo "[INFO] Status demona: $file"
      cat "$file"
    fi
  done
}

start_app() {
  ensure_runtime
  extract_addr "$@"
  if is_running; then
    load_addr
    echo "[INFO] Launcher już działa (PID $(cat "$PID_FILE"))."
    echo "[INFO] URL: http://${ADDRPORT}"
    exit 0
  fi

  echo "[INFO] Startuję aplikację przez start_demo_linux.sh"
  nohup "$PROJECT_DIR/start_demo_linux.sh" "$@" --noreload >"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "$ADDRPORT" > "$ADDR_FILE"

  local started=0
  for _ in $(seq 1 20); do
    if is_running && probe_http >/dev/null 2>&1; then
      started=1
      break
    fi
    if ! is_running; then
      break
    fi
    sleep 1
  done

  if [[ "$started" -eq 1 ]]; then
    echo "[OK] Uruchomiono launcher (PID $(cat "$PID_FILE"))."
    echo "[OK] Log: $LOG_FILE"
    echo "[OK] URL: http://${ADDRPORT}"
  else
    echo "[ERROR] Aplikacja nie zaczęła odpowiadać HTTP. Sprawdź log: $LOG_FILE" >&2
    stop_app >/dev/null 2>&1 || true
    exit 1
  fi
}

stop_app() {
  ensure_runtime
  load_addr
  if is_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    echo "[INFO] Zatrzymuję serwer Django (PID $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  else
    echo "[INFO] Serwer aplikacji nie działa."
    rm -f "$PID_FILE"
  fi
  rm -f "$ADDR_FILE"
  "$PROJECT_DIR/stop_demo_linux.sh" "$@"
}

status_app() {
  ensure_runtime
  load_addr
  if is_running; then
    echo "[OK] Serwer działa (PID $(cat "$PID_FILE"))."
    if probe_http >/dev/null 2>&1; then
      echo "[OK] HTTP odpowiada pod: http://${ADDRPORT}${PROBE_PATH}"
    else
      echo "[WARN] Proces istnieje, ale HTTP jeszcze nie odpowiada." >&2
    fi
  else
    echo "[INFO] Serwer nie działa."
  fi

  if command -v docker >/dev/null 2>&1 && docker inspect saldoflow-oracle >/dev/null 2>&1; then
    docker inspect --format '[INFO] Oracle: {{.State.Status}}' saldoflow-oracle
  else
    echo "[INFO] Oracle: brak kontenera lub nie dotyczy trybu SQLite."
  fi

  show_daemon_status
}

case "${1:-}" in
  start)
    shift
    start_app "$@"
    ;;
  stop)
    shift
    stop_app "$@"
    ;;
  restart)
    shift
    stop_app
    start_app "$@"
    ;;
  status)
    status_app
    ;;
  logs)
    ensure_runtime
    tail -n 80 -f "$LOG_FILE"
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
