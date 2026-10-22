"""Focused desktop checks; no native GUI or personal database is opened."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from webview.event import Event
from config import desktop


ROOT = Path(__file__).resolve().parent.parent


class DesktopPathTests(unittest.TestCase):
    def test_windowed_mode_does_not_require_console_streams(self):
        with patch.object(sys,'stdout',None),patch.object(sys,'stderr',None):
            desktop.ensure_streams()
            try:
                sys.stdout.write('no console required')
                sys.stderr.write('no console required')
            finally:
                sys.stdout.close();sys.stderr.close()

    def test_windows_data_is_per_user_outside_release(self):
        with patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA':'C:/Users/Example/AppData/Local'}):
            self.assertEqual(desktop.default_data_directory(),Path('C:/Users/Example/AppData/Local/StudentGradebook/data'))

    def test_source_environment_uses_separate_mutable_static_cache(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GRADEBOOK_DATA_DIR':temporary}):
            data=desktop.configure_environment()
            self.assertEqual(data,Path(temporary).resolve())
            self.assertEqual(os.environ['GRADEBOOK_STATIC_ROOT'],str(data/'cache/staticfiles'))
            self.assertTrue((data/'logs').is_dir())

    def test_frozen_resources_stay_in_bundle_but_database_does_not(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GRADEBOOK_DATA_DIR':temporary}), patch.object(sys, 'frozen', True, create=True):
            data=desktop.configure_environment()
            self.assertEqual(os.environ['GRADEBOOK_STATIC_ROOT'],str(desktop.RESOURCE_ROOT/'runtime/staticfiles'))
            command=desktop.worker_command(data/'config/desktop-test',123)
            self.assertEqual(command[0],sys.executable)
            self.assertNotIn(str(ROOT/'desktop_launcher.py'),command)
            self.assertEqual(command[-1],'123')

    def test_state_protocol_survives_incomplete_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            self.assertEqual(desktop.read_state(folder),{})
            (folder/'state.json').write_text('{')
            self.assertEqual(desktop.read_state(folder),{})
            desktop.write_state(folder,status='ready',url='http://127.0.0.1:12345/')
            self.assertEqual(desktop.read_state(folder)['status'],'ready')

    def test_instance_lock_is_exclusive_and_can_be_reacquired(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'desktop.lock'
            first=desktop.InstanceLock(path);second=desktop.InstanceLock(path)
            try:
                self.assertTrue(first.acquire())
                first.record_url('http://127.0.0.1:12345/')
                self.assertFalse(second.acquire())
                self.assertEqual(second.running_url(),'http://127.0.0.1:12345/')
                first.record_url('https://example.com/')
                self.assertIsNone(second.running_url())
                first.close()
                self.assertTrue(second.acquire())
            finally:
                first.close();second.close()


class DesktopWindowTests(unittest.TestCase):
    def window(self, folder):
        from config.desktop_window import DesktopWindow
        data=folder/'data';(data/'config').mkdir(parents=True)
        native=Mock();native.events.closing=Event(native,True);lock=Mock()
        window=DesktopWindow(native,data,lock)
        return window

    def test_close_callback_does_not_block_gui_or_evaluate_javascript(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=self.window(Path(temporary));session.ready=True
            self.assertFalse(session.on_closing())
            session.window.evaluate_js.assert_not_called()
            self.assertFalse(session.closing.is_set())
            session.window.evaluate_js.return_value=True
            session.check_close_request()
            self.assertTrue((session.folder/'stop').exists())
            session.window.destroy.assert_not_called()

    def test_ready_loads_embedded_window_once_and_shutdown_waits_for_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=self.window(Path(temporary))
            process=Mock();process.poll.side_effect=[None,None,0]
            desktop.write_state(session.folder,status='ready',url='http://127.0.0.1:12345/')
            def tick(_):
                session.window.destroy.assert_not_called()
                session.on_closing()
            with patch('config.desktop_window.subprocess.Popen',return_value=process),patch('config.desktop_window.time.sleep',side_effect=tick):
                session.run()
            session.window.load_url.assert_called_once_with('http://127.0.0.1:12345/')
            session.window.destroy.assert_called_once()
            self.assertTrue((session.folder/'stop').exists())
            process.terminate.assert_not_called();process.kill.assert_not_called()
            session.cleanup()
            session.lock.close.assert_called_once()
            self.assertFalse(session.folder.exists())

    def test_cancel_keeps_unsaved_score_page_and_worker_running(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=self.window(Path(temporary));session.ready=True
            session.window.evaluate_js.return_value=False
            session.window.create_confirmation_dialog.return_value=False
            session.on_closing();session.check_close_request()
            self.assertFalse(session.closing.is_set())
            self.assertFalse((session.folder/'stop').exists())
            session.window.destroy.assert_not_called()

    def test_closed_before_start_does_not_launch_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=self.window(Path(temporary));session.on_closing()
            with patch('config.desktop_window.subprocess.Popen') as popen:
                session.run()
                popen.assert_not_called()
            session.window.destroy.assert_called_once()
            session.cleanup()

    def test_second_launch_restores_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);session=self.window(folder)
            first=desktop.InstanceLock(session.data/'config/desktop.lock')
            second=desktop.InstanceLock(first.path)
            try:
                self.assertTrue(first.acquire());first.record_url('',session.folder)
                self.assertFalse(second.acquire());self.assertTrue(second.request_activation())
                session.activate()
                session.window.restore.assert_called_once()
                session.window.show.assert_called_once()
                self.assertFalse((session.folder/'activate').exists())
                first.record_url('',folder)
                self.assertFalse(second.request_activation())
            finally:
                first.close();second.close()

    def test_start_failure_is_visible_in_window_and_html_is_escaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=self.window(Path(temporary))
            with patch('config.desktop_window.subprocess.Popen',side_effect=OSError('<script>bad</script>')):
                session.run()
            html=session.window.load_html.call_args.args[0]
            self.assertIn('&lt;script&gt;',html)
            self.assertNotIn('<script>bad</script>',html)
            self.assertTrue(session.finished.is_set())
            self.assertTrue(session.on_closing())
            session.cleanup()


class DesktopExportTests(unittest.TestCase):
    def test_export_saves_original_post_bytes_and_cancel_preserves_file(self):
        import base64
        from config.desktop_window import ExportBridge
        bridge=ExportBridge();bridge._window=Mock()
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'รายงาน.xlsx';target.write_bytes(b'previous')
            bridge._window.create_file_dialog.return_value=None
            encoded=base64.b64encode(b'original POST response').decode()
            self.assertEqual(bridge.save_report('scores.xlsx',encoded),{'saved':False})
            self.assertEqual(target.read_bytes(),b'previous')
            bridge._window.create_file_dialog.return_value=(str(target),)
            self.assertEqual(bridge.save_report('scores.xlsx',encoded),{'saved':True})
            self.assertEqual(target.read_bytes(),b'original POST response')
            self.assertEqual(list(Path(temporary).iterdir()),[target])

    def test_invalid_payload_does_not_open_save_dialog_or_replace_file(self):
        from config.desktop_window import ExportBridge
        bridge=ExportBridge();bridge._window=Mock()
        with self.assertRaises(ValueError):bridge.save_report('report.exe','YWJj')
        with self.assertRaises(ValueError):bridge.save_report('report.docx','not base64!')
        bridge._window.create_file_dialog.assert_not_called()


class DesktopWorkerTests(unittest.TestCase):
    def tearDown(self):
        logging.shutdown()

    def test_stop_finishes_work_and_binds_only_to_loopback(self):
        from config.desktop_server import run_worker
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GRADEBOOK_DATA_DIR':temporary}):
            data=Path(temporary);folder=data/'config/desktop-test';folder.mkdir(parents=True)
            server=Mock();server.effective_port=12345
            import threading
            server.task_dispatcher.lock=threading.Lock()
            server.task_dispatcher.queue=[];server.task_dispatcher.active_count=0
            with patch('config.desktop_server.prepare_database'), patch('config.desktop_server.ParentWatch') as watch, patch('django.core.wsgi.get_wsgi_application',return_value=Mock()), patch('waitress.create_server',return_value=server) as create, patch('waitress.wasyncore.loop',side_effect=lambda **kwargs:(folder/'stop').touch()):
                watch.return_value.alive.return_value=True
                self.assertEqual(run_worker(folder,123),0)
                self.assertEqual(create.call_args.kwargs['host'],'127.0.0.1')
                self.assertEqual(create.call_args.kwargs['port'],0)
                self.assertEqual(desktop.read_state(folder)['status'],'stopped')
                self.assertFalse(server.accepting)
                server.task_dispatcher.shutdown.assert_any_call(cancel_pending=False,timeout=5)

    def test_parent_exit_prevents_orphan_server(self):
        from config.desktop_server import run_worker
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GRADEBOOK_DATA_DIR':temporary}):
            folder=Path(temporary)/'config/desktop-test';folder.mkdir(parents=True)
            with patch('config.desktop_server.ParentWatch') as watch, patch('config.desktop_server.prepare_database') as prepare:
                watch.return_value.alive.return_value=False
                self.assertEqual(run_worker(folder,123),0)
                prepare.assert_not_called()

    def test_errors_are_visible_in_state_file_without_stdout(self):
        from config.desktop_server import run_worker
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GRADEBOOK_DATA_DIR':temporary}):
            folder=Path(temporary)/'config/desktop-test';folder.mkdir(parents=True)
            with patch('config.desktop_server.ParentWatch') as watch, patch('config.desktop_server.prepare_database',side_effect=RuntimeError('Example startup failure')):
                watch.return_value.alive.return_value=True
                self.assertEqual(run_worker(folder,123),1)
                self.assertEqual(desktop.read_state(folder)['message'],'Example startup failure')


class DesktopDatabaseTests(unittest.TestCase):
    def test_clean_database_and_backup_before_pending_upgrade(self):
        code='''from pathlib import Path
import os,sqlite3
from unittest.mock import patch,Mock
from config.desktop import configure_environment
from config.desktop_server import prepare_database
data=configure_environment()
prepare_database(data,lambda message:None)
from apps.assessments.models import MarkingSchemeCategory
from apps.teachers.models import TeacherProfile
assert MarkingSchemeCategory.objects.count()==4
TeacherProfile.objects.create(name='Desktop example',academic_status='Teacher')
with patch('django.db.migrations.executor.MigrationExecutor') as executor:
    executor.return_value.migration_plan.return_value=[Mock()]
    prepare_database(data,lambda message:None)
backups=list((data/'backups').glob('*.sqlite3'))
assert len(backups)==1
with sqlite3.connect(backups[0]) as connection:
    assert connection.execute('SELECT name FROM teachers_teacherprofile').fetchone()[0]=='Desktop example'
assert TeacherProfile.objects.get().name=='Desktop example'
print('Fresh database and migration backup reviewed.')
'''
        with tempfile.TemporaryDirectory() as temporary:
            environment={**os.environ,'GRADEBOOK_DATA_DIR':temporary,'PYTHONPATH':str(ROOT)}
            result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=environment,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':
    unittest.main()
