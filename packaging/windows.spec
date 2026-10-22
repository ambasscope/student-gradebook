# -*- mode: python ; coding: utf-8 -*-
"""One-folder Windows release. Resources are allowlisted; user data is excluded."""
import os
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from config.desktop_checks import dynamic_import_modules
STATIC = Path(os.environ['GRADEBOOK_BUILD_STATIC_DIR'])
if not (STATIC / 'css' / 'app.css').is_file():
    raise RuntimeError('Run tools/build_windows.py to collect static assets first.')

def wanted(module):
    return 'tests' not in module.split('.') and not module.endswith('.admin')

hidden = collect_submodules('apps', filter=wanted, on_error='raise')
hidden += collect_submodules('config', filter=lambda name: not any(part.startswith('test') for part in name.split('.')), on_error='raise')
for package in ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                'django.contrib.messages', 'django.contrib.staticfiles', 'django.db.backends.sqlite3',
                'django.db.migrations', 'django.templatetags', 'django.core.management.commands']:
    hidden += collect_submodules(package, filter=wanted)
hidden += ['django.template.backends.django', 'django.views.i18n', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox']
# Middleware is loaded from dotted strings in settings, rather than Python
# imports. Distribution metadata alone does not bundle the implementation.
hidden += dynamic_import_modules()
hidden += collect_submodules('whitenoise', on_error='raise')
hidden += ['webview.platforms.winforms', 'webview.platforms.edgechromium', 'clr_loader']
data = [(str(ROOT / 'templates'), 'templates'), (str(ROOT / 'locale'), 'locale'),
        (str(STATIC), 'runtime/staticfiles')]
data += collect_data_files('apps', include_py_files=True, includes=[
    '**/templates/**', '**/migrations/*.py', '**/document_templates/**',
    '**/spreadsheet_templates/**', '**/data/*.json'])
data += collect_data_files('django')
data += collect_data_files('django', include_py_files=True, includes=['**/migrations/*.py'])
data += collect_data_files('docx')
data += collect_data_files('webview')
for package in ['Django', 'docxtpl', 'python-docx', 'waitress', 'whitenoise', 'openpyxl', 'xlrd', 'pywebview']:
    data += copy_metadata(package)

a = Analysis([str(ROOT / 'desktop_launcher.py')], pathex=[str(ROOT)], binaries=collect_dynamic_libs('webview'), datas=data,
             hiddenimports=sorted(set(hidden)), hookspath=[], runtime_hooks=[], excludes=['pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StudentGradebook',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, contents_directory='_internal',
          version=str(ROOT / 'packaging/windows-version-info.txt'))
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='StudentGradebook')
