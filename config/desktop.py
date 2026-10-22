"""Desktop paths, per-user instance lock and console-free process communication."""
import json
import os
from pathlib import Path
import sys
import time

APP_NAME = 'Student Gradebook'
RESOURCE_ROOT = Path(__file__).resolve().parent.parent


def default_data_directory():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'StudentGradebook' / 'data'


def configure_environment():
    configured = os.environ.get('GRADEBOOK_DATA_DIR')
    data = Path(configured).expanduser() if configured else default_data_directory()
    if not data.is_absolute():
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else RESOURCE_ROOT
        data = base / data
    data = data.resolve()
    for name in ['', 'reports', 'backups', 'config', 'logs']:
        (data / name).mkdir(parents=True, exist_ok=True)
    os.environ['GRADEBOOK_DATA_DIR'] = str(data)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    os.environ['DJANGO_DEBUG'] = '0'
    static = RESOURCE_ROOT / 'runtime' / 'staticfiles' if getattr(sys, 'frozen', False) else data / 'cache' / 'staticfiles'
    os.environ['GRADEBOOK_STATIC_ROOT'] = str(static)
    return data


def ensure_streams():
    # pythonw/PyInstaller --windowed may set these to None even when inherited
    # handles were supplied. Lifecycle messages therefore use files, not pipes.
    for name in ['stdout', 'stderr']:
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w', encoding='utf-8'))


def write_state(folder, **state):
    temporary = folder / 'state.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    for attempt in range(10):
        try:
            temporary.replace(folder / 'state.json')
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def read_state(folder):
    try:
        state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


class InstanceLock:
    """OS-released lock: a crash cannot leave a stale lock blocking the app."""
    def __init__(self, path):
        self.path = path
        self.stream = None

    def acquire(self):
        stream = open(self.path, 'a+b')
        if not self.path.stat().st_size:
            stream.write(b' '); stream.flush()
        stream.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.stream = stream
        self.record_url('')
        return True

    def record_url(self, url, session=None):
        # Byte zero is reserved for the Windows lock.
        self.stream.seek(1)
        self.stream.truncate()
        self.stream.write(json.dumps({'url': url, 'session': str(session) if session else ''}).encode('utf-8'))
        self.stream.flush()

    def request_activation(self):
        """Ask the owner to restore its window, without opening a browser."""
        try:
            with open(self.path, 'rb') as stream:
                stream.seek(1)
                session = Path(json.loads(stream.read())['session'])
            if session.parent.resolve() != self.path.parent.resolve() or not session.name.startswith('desktop-') or not session.is_dir():
                return False
            (session / 'activate').touch()
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def running_url(self):
        import re
        try:
            with open(self.path, 'rb') as stream:
                stream.seek(1)
                url = json.loads(stream.read()).get('url', '')
            match = re.fullmatch(r'http://127\.0\.0\.1:([0-9]{1,5})/', url)
            return url if match and 1 <= int(match[1]) <= 65535 else None
        except (OSError, ValueError, AttributeError, TypeError):
            return None

    def close(self):
        if self.stream is not None:
            self.record_url('')
            self.stream.close()
            self.stream = None


def worker_command(folder, parent_pid):
    args = ['--desktop-server', str(folder), '--parent-pid', str(parent_pid)]
    if getattr(sys, 'frozen', False):
        return [sys.executable, *args]
    return [sys.executable, str(RESOURCE_ROOT / 'desktop_launcher.py'), *args]
