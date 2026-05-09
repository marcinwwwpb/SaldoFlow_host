from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from demon.management.commands.runserver_with_daemon import Command


@override_settings(BASE_DIR='/tmp/saldoflow')
class RunserverWithDaemonTests(SimpleTestCase):
    def test_start_command_runs_daemon_in_foreground_and_passes_archives(self):
        command = Command()
        fake_proc = MagicMock(pid=1234)
        options = {
            'modules': ['dom'],
            'dom_watchdir': '/tmp/watch/dom',
            'firma_watchdir': '/tmp/watch/firma',
            'status_dir': '/tmp/status',
            'archive_dir': '/tmp/archive',
            'daemon_user': 'tester',
        }

        with patch('demon.management.commands.runserver_with_daemon.Path.exists', return_value=True), patch(
            'demon.management.commands.runserver_with_daemon.subprocess.Popen', return_value=fake_proc
        ) as popen:
            command._start_daemons(options)

        self.assertEqual(popen.call_count, 1)
        args = popen.call_args.args[0]
        self.assertIn('--foreground', args)
        self.assertIn('--archive-ok', args)
        self.assertIn('/tmp/archive/dom/ok', args)
        self.assertIn('--archive-error', args)
        self.assertIn('/tmp/archive/dom/error', args)

    def test_stop_daemons_kills_process_group(self):
        command = Command()
        fake_proc = MagicMock(pid=1234)
        command._daemon_processes = [fake_proc]
        command._daemons_started = True

        with patch('demon.management.commands.runserver_with_daemon.os.getpgid', return_value=4321), patch(
            'demon.management.commands.runserver_with_daemon.os.killpg'
        ) as killpg:
            command._stop_daemons()

        killpg.assert_called_once()
        fake_proc.wait.assert_called_once()
        self.assertEqual(command._daemon_processes, [])
        self.assertFalse(command._daemons_started)
