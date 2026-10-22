"""Exercise the packaged runtime without a GUI, socket, or personal database."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import traceback
from .desktop import configure_environment, ensure_streams


def dynamic_import_modules(settings_module='config.settings'):
    settings = importlib.import_module(settings_module)
    paths = list(settings.MIDDLEWARE)
    paths.extend(template['BACKEND'] for template in settings.TEMPLATES)
    # Django imports these class paths from strings; PyInstaller needs their modules.
    return sorted({path.rsplit('.', 1)[0] for path in paths})


def check_dynamic_imports():
    for module in dynamic_import_modules():
        importlib.import_module(module)


def check_desktop_dependencies():
    import sys
    import webview
    # No GUI initialization. Verify dynamically selected native dependencies
    # before publishing the executable, in addition to Django's middleware.
    if sys.platform == 'win32':
        importlib.import_module('webview.platforms.edgechromium')
        native = importlib.import_module('webview.platforms.winforms')
        if native.renderer != 'edgechromium':
            raise RuntimeError('Microsoft Edge WebView2 Runtime is required. Install it and reopen the app.')


def request(application, path):
    from io import BytesIO
    from wsgiref.util import setup_testing_defaults
    environment = {}
    setup_testing_defaults(environment)
    environment.update(PATH_INFO=path, HTTP_HOST='127.0.0.1', SERVER_NAME='127.0.0.1',
                       REQUEST_METHOD='GET', HTTP_COOKIE='', **{'wsgi.input':BytesIO()})
    response = {}
    def start_response(status, headers, exc_info=None):
        response['status'] = status
    iterable = application(environment, start_response)
    try:
        size = sum(len(part) for part in iterable)
    finally:
        if hasattr(iterable, 'close'):
            iterable.close()
    if not response.get('status', '').startswith('200 ') or not size:
        raise RuntimeError(f'Packaged request failed: {path}: {response.get("status")} ({size} bytes)')


def run_check(result_path):
    ensure_streams()
    result = {'ok':False}
    try:
        # Always create a temporary database, even when a user data override is set.
        # This command never migrates, reads, or replaces the user's database.
        with tempfile.TemporaryDirectory(prefix='gradebook-selfcheck-') as temporary:
            os.environ['GRADEBOOK_DATA_DIR'] = str(Path(temporary) / 'data')
            data = configure_environment()
            from .desktop_server import prepare_database
            try:
                prepare_database(data, lambda message:None)
                check_dynamic_imports()
                check_desktop_dependencies()
                from django.core.wsgi import get_wsgi_application
                from django.template.loader import get_template
                from django.utils.translation import override
                application = get_wsgi_application()
                with override('en'):
                    request(application, '/')
                request(application, '/static/css/app.css')
                request(application, '/static/js/desktop.js')
                request(application, '/jsi18n/')
                for template in ['assessments/edit.html', 'assessments/evaluation_rubric.html',
                                 'reports/module_record.html', 'reports/student_scores.html', 'students/edit.html', 'delete_confirm.html']:
                    get_template(template)
                result = {'ok':True, 'checks':['database migrations','middleware imports','homepage',
                          'static assets','JavaScript catalog','templates and custom tags','pywebview imports']}
            finally:
                from django.db import connections
                connections.close_all()
    except Exception:
        result = {'ok':False, 'error':traceback.format_exc()}
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1
