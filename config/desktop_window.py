"""Embedded desktop window for the existing Django application."""
from html import escape
import base64
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from .desktop import APP_NAME, InstanceLock, configure_environment, read_state, worker_command


def open_folder(folder):
    if sys.platform == 'win32':
        os.startfile(str(folder))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])


def status_page(title, message, logs=None):
    """Local loading/error page. Escape worker messages before rendering them."""
    detail = '<p>Logs / บันทึกข้อผิดพลาด</p><pre>'+escape(str(logs))+'</pre>' if logs else ''
    return '''<!doctype html><html lang="th"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Student Gradebook</title><style>
body{font:17px/1.7 system-ui,sans-serif;background:#f5f7fb;color:#182333;margin:0;
min-height:100vh;display:grid;place-items:center}main{max-width:760px;padding:40px}
h1{font-size:28px}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}pre{font-size:14px}
</style><main><h1>'''+escape(title)+'</h1><p>'+escape(message)+'</p>'+detail+'</main></html>'


class DesktopWindow:
    """Monitor the existing worker off the main GUI thread.

    Closing is deferred until the worker has finished accepted requests. This
    also keeps the instance lock held while saves and report generation finish.
    """
    def __init__(self, window, data, lock):
        self.window, self.data, self.lock = window, data, lock
        self.process, self.url = None, None
        self.ready = False
        self.closing = threading.Event()
        self.close_requested = threading.Event()
        self.finished = threading.Event()
        self.run_started = threading.Event()
        self.run_done = threading.Event()
        self.cleanup_started = threading.Event()
        self.lifecycle_lock = threading.Lock()
        self.folder = Path(tempfile.mkdtemp(prefix='desktop-', dir=data / 'config'))
        self.lock.record_url('', self.folder)
        window.events.closing += self.on_closing
        self.last_message = None

    def show_status(self, title, message, logs=None):
        if self.last_message == (title, message, logs):
            return
        self.last_message = (title, message, logs)
        self.window.load_html(status_page(title, message, logs))

    def on_closing(self):
        if self.finished.is_set():
            return True
        # This event runs synchronously on the native UI thread. JavaScript and
        # dialogs must run from the monitor after this handler returns.
        self.close_requested.set()
        return False

    def check_close_request(self):
        if not self.close_requested.is_set() or self.closing.is_set():
            return
        self.close_requested.clear()
        if self.ready:
            try:
                clean = self.window.evaluate_js("window.dispatchEvent(new CustomEvent('gradebook:before-close', {cancelable:true}))")
                if clean is False and not self.window.create_confirmation_dialog(APP_NAME,
                        'Discard unsaved changes and close?\nต้องการปิดแอปโดยไม่บันทึกการเปลี่ยนแปลงหรือไม่?'):
                    return False
            except Exception:
                logging.exception('Could not check unsaved edits')
                if not self.window.create_confirmation_dialog(APP_NAME,
                        'Save your work before closing. Close now?\nกรุณาบันทึกงานก่อนปิดแอป ต้องการปิดตอนนี้หรือไม่?'):
                    return False
        self.closing.set()
        (self.folder / 'stop').touch()
        # The monitor owns shutdown and destroys the window when the worker exits.
        # Do not navigate away from a live page until its accepted requests finish.

    def quit(self):
        if self.on_closing():
            self.window.destroy()

    def show_data(self):
        try:
            open_folder(self.data)
        except Exception:
            logging.exception('Could not open data folder')

    def activate(self):
        request = self.folder / 'activate'
        if request.exists():
            request.unlink(missing_ok=True)
            self.window.restore()
            self.window.show()

    def run(self):
        self.run_started.set()
        try:
            with self.lifecycle_lock:
                if self.closing.is_set():
                    self.finished.set()
                    if not self.cleanup_started.is_set():
                        self.window.destroy()
                    return
                if self.close_requested.is_set():
                    self.closing.set()
                    self.finished.set()
                    self.window.destroy()
                    return
                options = {'stdin':subprocess.DEVNULL, 'stdout':subprocess.DEVNULL,
                           'stderr':subprocess.DEVNULL, 'cwd':str(self.data),
                           'env':os.environ.copy()}
                if sys.platform == 'win32':
                    options['creationflags'] = subprocess.CREATE_NO_WINDOW
                self.process = subprocess.Popen(worker_command(self.folder, os.getpid()), **options)
            while self.process is not None:
                state = read_state(self.folder)
                self.activate()
                self.check_close_request()
                if self.closing.is_set():
                    (self.folder / 'stop').touch()
                elif state.get('status') == 'ready' and not self.ready:
                    self.url = state['url']
                    self.lock.record_url(self.url, self.folder)
                    self.window.load_url(self.url)
                    self.ready = True
                elif state.get('status') == 'starting':
                    self.show_status(APP_NAME, state.get('message', 'Starting… / กำลังเปิดแอป…'))
                if self.process.poll() is not None:
                    self.finished.set()
                    if self.closing.is_set():
                        self.window.destroy()
                    else:
                        self.show_status('Could not start / ไม่สามารถเปิดแอปได้',
                                         state.get('message') or 'The background server stopped unexpectedly.',
                                         self.data / 'logs')
                    return
                time.sleep(0.2)
            self.finished.set()
            if self.closing.is_set():
                self.window.destroy()
        except Exception as error:
            logging.exception('Desktop window failed')
            # Even if a GUI operation fails, stop the server before releasing its lock.
            (self.folder / 'stop').touch()
            if self.process is not None:
                self.process.wait()
            self.finished.set()
            if self.closing.is_set():
                self.window.destroy()
            else:
                self.show_status('Could not start / ไม่สามารถเปิดแอปได้', str(error), self.data / 'logs')
        finally:
            self.run_done.set()

    def cleanup(self):
        with self.lifecycle_lock:
            self.cleanup_started.set()
            self.closing.set()
            (self.folder / 'stop').touch()
        if self.process is not None:
            self.process.wait()
        if self.run_started.is_set():
            self.run_done.wait()
        self.lock.close()
        shutil.rmtree(self.folder, ignore_errors=True)


def show_startup_error(message):
    # A native fallback is needed if the web engine itself cannot initialize.
    # Tk is used only for this error dialog, never as a second application window.
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror(APP_NAME, message, parent=root)
    finally:
        root.destroy()


class ExportBridge:
    """Save an already generated response; never retry a POST export as GET."""
    def __init__(self):
        self._window = None

    def save_report(self, filename, encoded):
        name = str(filename).replace('\\', '/').rsplit('/', 1)[-1]
        if Path(name).suffix.lower() not in {'.docx', '.xlsx'}:
            raise ValueError('Unsupported report format.')
        payload = base64.b64decode(encoded, validate=True)
        import webview
        selection = self._window.create_file_dialog(webview.FileDialog.SAVE,
            save_filename=name, file_types=('Reports (*.docx;*.xlsx)',))
        if not selection:
            return {'saved': False}
        destination = Path(selection[0])
        if not destination.suffix:
            destination = destination.with_suffix(Path(name).suffix)
        # Keep any existing file intact if writing fails.
        descriptor, temporary = tempfile.mkstemp(prefix='.gradebook-', dir=destination.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payload)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {'saved': True}


def run_window():
    lock, session = None, None
    try:
        data = configure_environment()
        handler = RotatingFileHandler(data / 'logs' / 'launcher.log', maxBytes=1_000_000,
                                      backupCount=2, encoding='utf-8')
        logging.basicConfig(level=logging.INFO, handlers=[handler],
                            format='%(asctime)s %(levelname)s %(message)s', force=True)
        lock = InstanceLock(data / 'config' / 'desktop.lock')
        if not lock.acquire():
            lock.request_activation()
            return 0
        import webview
        from webview.menu import Menu, MenuAction
        if sys.platform == 'win32':
            from .desktop_checks import check_desktop_dependencies
            check_desktop_dependencies()
        webview.settings['ALLOW_DOWNLOADS'] = True
        bridge = ExportBridge()
        window = webview.create_window(APP_NAME, js_api=bridge,
            html=status_page(APP_NAME, 'Starting… / กำลังเปิดแอป…'),
            width=1280, height=850, min_size=(900, 650), text_select=True)
        bridge._window = window
        session = DesktopWindow(window, data, lock)
        menu = [Menu(APP_NAME, [MenuAction('Data folder / โฟลเดอร์ข้อมูล', session.show_data),
                               MenuAction('Quit / ปิดแอป', session.quit)])]
        # Explicitly require a modern renderer. Never fall back to old IE/MSHTML.
        webview.start(session.run, gui='edgechromium' if sys.platform == 'win32' else ('cocoa' if sys.platform == 'darwin' else None),
                      private_mode=True, menu=menu)
        return 0
    except Exception as error:
        logging.exception('Desktop startup failed')
        message = 'Could not start / ไม่สามารถเปิดแอปได้\n\n'+str(error)
        if sys.platform == 'win32':
            message += '\n\nInstall Microsoft Edge WebView2 Runtime, then reopen the app.\nกรุณาติดตั้ง Microsoft Edge WebView2 Runtime แล้วเปิดแอปอีกครั้ง'
        if 'data' in locals():
            message += '\n\nLogs / บันทึกข้อผิดพลาด:\n'+str(data / 'logs')
        show_startup_error(message)
        return 1
    finally:
        if session is not None:
            session.cleanup()
        elif lock is not None:
            lock.close()
