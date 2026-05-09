import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import AdminAuditLog


def _status_files():
    status_dir = Path(getattr(settings, "DEMON_STATUS_DIR", "/tmp"))
    return {
        "dom": status_dir / "import_watchd_dom.json",
        "firma": status_dir / "import_watchd_firma.json",
    }


def read_daemon_statuses():
    statuses = []
    for module, path in _status_files().items():
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("module", module)
                data["status_file"] = str(path)
                statuses.append(data)
                continue
            except Exception:
                pass
        statuses.append({
            "module": module,
            "running": False,
            "last_error": "Brak pliku statusu demona.",
            "status_file": str(path),
        })
    return statuses


def audit_log(*, actor=None, module, entity_type, entity_id=None, action, payload=None):
    return AdminAuditLog.objects.create(
        actor=actor,
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload=payload or {},
    )



def _service_name(module):
    return (getattr(settings, 'DEMON_SERVICES', {}) or {}).get(module, '')


def _default_status(module):
    return {
        'module': module,
        'running': False,
        'enabled': False,
        'desired_state': 'disabled',
        'last_error': 'Brak pliku statusu demona.',
        'status_file': str(_status_files()[module]),
        'service_name': _service_name(module),
    }


def read_daemon_status(module):
    path = _status_files()[module]
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            data.setdefault('module', module)
            data.setdefault('service_name', _service_name(module))
            data.setdefault('desired_state', 'enabled' if data.get('running') else 'disabled')
            data.setdefault('enabled', bool(data.get('running')))
            data['status_file'] = str(path)
            return data
        except Exception:
            pass
    return _default_status(module)


def write_daemon_status(module, payload):
    path = _status_files()[module]
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read_daemon_status(module)
    current.update(payload)
    current['module'] = module
    current['service_name'] = _service_name(module)
    current['status_file'] = str(path)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    return current


def _run_systemctl(command, service_name):
    if not service_name or not shutil.which('systemctl'):
        return False, 'Sterowanie usługą systemową nie jest dostępne w tym środowisku.'
    result = subprocess.run(['systemctl', command, service_name], capture_output=True, text=True)
    if result.returncode == 0:
        return True, f'Wykonano: systemctl {command} {service_name}'
    message = (result.stderr or result.stdout or 'Nie udało się wykonać polecenia systemctl.').strip()
    return False, message


def control_daemon(module, action):
    if module not in _status_files():
        raise KeyError(module)
    if action not in {'enable', 'disable', 'reset'}:
        raise ValueError(action)

    service_name = _service_name(module)
    if action == 'enable':
        system_ok, system_message = _run_systemctl('start', service_name)
        status = write_daemon_status(module, {
            'enabled': True,
            'running': True if system_ok else read_daemon_status(module).get('running', False),
            'desired_state': 'enabled',
            'last_control_action': 'enable',
            'controlled_at': timezone.now().isoformat(),
            'last_error': '' if system_ok else system_message,
        })
    elif action == 'disable':
        system_ok, system_message = _run_systemctl('stop', service_name)
        status = write_daemon_status(module, {
            'enabled': False,
            'running': False,
            'desired_state': 'disabled',
            'last_control_action': 'disable',
            'controlled_at': timezone.now().isoformat(),
            'last_error': '' if system_ok else system_message,
        })
    else:
        system_ok, system_message = _run_systemctl('restart', service_name)
        status = write_daemon_status(module, {
            'enabled': True,
            'running': True if system_ok else read_daemon_status(module).get('running', False),
            'desired_state': 'enabled',
            'last_control_action': 'reset',
            'controlled_at': timezone.now().isoformat(),
            'last_reset_at': timezone.now().isoformat(),
            'last_error': '' if system_ok else system_message,
        })

    return {
        'status': status,
        'system_ok': system_ok,
        'message': system_message,
        'service_name': service_name,
    }
