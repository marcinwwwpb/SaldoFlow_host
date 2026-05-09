import os
import signal
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as StaticRunserverCommand


class Command(StaticRunserverCommand):
    help = "Uruchamia demony importu i następnie startuje Django runserver."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._daemon_processes = []
        self._daemons_started = False

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--module", choices=["dom", "firma"], action="append", dest="modules")
        parser.add_argument("--dom-watchdir", default=str(settings.BASE_DIR / "runtime" / "watch" / "dom"))
        parser.add_argument("--firma-watchdir", default=str(settings.BASE_DIR / "runtime" / "watch" / "firma"))
        parser.add_argument("--status-dir", default=str(settings.BASE_DIR / "runtime" / "daemon_status"))
        parser.add_argument("--archive-dir", default=str(settings.BASE_DIR / "runtime" / "archive"))
        parser.add_argument("--daemon-user", default=os.getenv("DAEMON_IMPORT_USER") or os.getenv("USER", "operator"))

    def inner_run(self, *args, **options):
        if not self._daemons_started:
            self._start_daemons(options)
            self._daemons_started = True
        try:
            return super().inner_run(*args, **options)
        finally:
            self._stop_daemons()

    def _start_daemons(self, options):
        modules = options.get("modules") or ["dom", "firma"]
        base_dir = Path(settings.BASE_DIR)
        demon_bin = base_dir / "demon" / "import_watchd"
        manage_py = base_dir / "manage.py"
        python_bin = Path(sys.executable)

        if not demon_bin.exists():
            self.stderr.write(self.style.ERROR(f"Nie znaleziono demona: {demon_bin}"))
            return

        status_dir = Path(options["status_dir"])
        archive_root = Path(options["archive_dir"])
        dom_watchdir = Path(options["dom_watchdir"])
        firma_watchdir = Path(options["firma_watchdir"])
        daemon_user = options["daemon_user"]

        status_dir.mkdir(parents=True, exist_ok=True)
        dom_watchdir.mkdir(parents=True, exist_ok=True)
        firma_watchdir.mkdir(parents=True, exist_ok=True)

        for module in modules:
            watchdir = dom_watchdir if module == "dom" else firma_watchdir
            archive_ok = archive_root / module / "ok"
            archive_error = archive_root / module / "error"
            archive_ok.mkdir(parents=True, exist_ok=True)
            archive_error.mkdir(parents=True, exist_ok=True)

            cmd = [
                str(demon_bin),
                str(watchdir),
                str(python_bin),
                str(manage_py),
                daemon_user,
                "--module",
                module,
                "--status-dir",
                str(status_dir),
                "--archive-ok",
                str(archive_ok),
                "--archive-error",
                str(archive_error),
                "--foreground",
            ]
            self.stdout.write(f"Uruchamiam demona: {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._daemon_processes.append(proc)

        if self._daemon_processes:
            self.stdout.write(self.style.SUCCESS("Demony importu zostały uruchomione."))

    def _stop_daemons(self):
        if not self._daemon_processes:
            return

        self.stdout.write(self.style.WARNING("Zatrzymuję demony importu..."))
        for proc in self._daemon_processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                continue
            except Exception:
                continue
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

        self._daemon_processes = []
        self._daemons_started = False
