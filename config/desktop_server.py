"""Background Waitress worker, controlled by a launcher window without a console."""
from datetime import datetime, timezone
from io import StringIO
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sqlite3
import sys
from .desktop import configure_environment, ensure_streams, write_state


class ParentWatch:
    def __init__(self, pid):
        self.pid, self.handle = pid, None
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            self.kernel.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.handle = self.kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE

    def alive(self):
        if sys.platform == 'win32':
            return bool(self.handle) and self.kernel.WaitForSingleObject(self.handle, 0) == 0x00000102
        return os.getppid() == self.pid

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)


def prepare_database(data, notify):
    import django
    from django.core.management import call_command
    database = data / 'db.sqlite3'
    existed = database.exists() and database.stat().st_size > 0
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan and existed:
        notify('Backing up your database… / กำลังสำรองฐานข้อมูล…')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(data / 'backups' / f'before-desktop-migration-{stamp}.sqlite3') as target:
            source.backup(target)
    notify('Preparing your database… / กำลังเตรียมฐานข้อมูล…')
    call_command('check', stdout=StringIO(), stderr=StringIO())
    call_command('migrate', interactive=False, verbosity=0, stdout=StringIO(), stderr=StringIO())
    if not getattr(sys, 'frozen', False):
        call_command('collectstatic', interactive=False, verbosity=0, stdout=StringIO(), stderr=StringIO())
    from django.conf import settings
    if not (settings.STATIC_ROOT / 'css' / 'app.css').is_file():
        raise RuntimeError('Bundled static files are missing. Rebuild the application folder.')
    connection.close()


def run_worker(folder, parent_pid):
    ensure_streams()
    data = configure_environment()
    folder = Path(folder).resolve()
    if folder.parent != (data / 'config').resolve() or not folder.name.startswith('desktop-') or not folder.is_dir():
        raise ValueError('Invalid desktop session directory.')
    handler = RotatingFileHandler(data / 'logs' / 'server.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s', force=True)
    watch = ParentWatch(parent_pid)
    server, socket_map = None, {}
    stopping = lambda: (folder / 'stop').exists() or not watch.alive()
    notify = lambda message: write_state(folder, status='starting', message=message)
    try:
        if stopping():
            return 0
        prepare_database(data, notify)
        if stopping():
            return 0
        from django.core.wsgi import get_wsgi_application
        from waitress import create_server, wasyncore
        # Port zero lets the OS choose a free local port; it avoids collisions
        # with the development server and other applications.
        server = create_server(get_wsgi_application(), host='127.0.0.1', port=0, map=socket_map, threads=4)
        url = f'http://127.0.0.1:{server.effective_port}/'
        write_state(folder, status='ready', url=url)
        while not stopping():
            wasyncore.loop(timeout=0.2, count=1, map=socket_map)
        write_state(folder, status='stopping', message='Finishing saves… / กำลังบันทึกให้เสร็จ…')
        server.accepting = False  # Keep the trigger alive while existing tasks finish.
        # Finish accepted work before ending database worker threads. A slow
        # report/save keeps the launcher in Closing, rather than being killed.
        while True:
            with server.task_dispatcher.lock:
                busy = bool(server.task_dispatcher.queue or server.task_dispatcher.active_count)
            if not busy:
                break
            wasyncore.loop(timeout=0.1, count=1, map=socket_map)
        server.task_dispatcher.shutdown(cancel_pending=False, timeout=5)
        write_state(folder, status='stopped')
        return 0
    except Exception as error:
        logging.exception('Desktop server failed')
        write_state(folder, status='error', message=str(error))
        return 1
    finally:
        try:
            if server is not None:
                server.close()
                server.task_dispatcher.shutdown(timeout=5)
            for channel in list(socket_map.values()):
                channel.close()
        finally:
            watch.close()
            # Windows cannot remove a data folder while its log file is open.
            logging.getLogger().removeHandler(handler)
            handler.close()
