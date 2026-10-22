"""Build on Windows; --check-only reviews resources on any OS without PyInstaller."""
import argparse
import hashlib
import json
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_resources():
    required = [
        'desktop_launcher.py', 'config/desktop.py', 'config/desktop_server.py', 'config/desktop_window.py',
        'requirements-desktop.txt', 'static/js/desktop.js',
        'apps/students/migrations/0004_student_resignation_date_student_status_and_more.py',
        'static/js/student-form.js', 'config/deletion.py', 'config/deletion_views.py', 'templates/delete_confirm.html',
        'templates/base.html', 'static/css/app.css', 'static/js/assignment-scores.js',
        'locale/th/LC_MESSAGES/django.mo', 'locale/th/LC_MESSAGES/djangojs.mo',
        'apps/assessments/data/marking-scheme_kpac.json',
        'apps/reports/document_templates/module-record.docx', 'apps/reports/document_templates/line-widths.json',
        'apps/reports/spreadsheet_templates/score-styles.xlsx', 'apps/reports/spreadsheet_templates/style-cells.json']
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError('Missing required resources: '+', '.join(missing))
    # Do not require GNU gettext on Windows when shipping already compiled catalogs.
    for po in (ROOT / 'locale').rglob('*.po'):
        mo = po.with_suffix('.mo')
        if not mo.exists() or po.stat().st_mtime > mo.stat().st_mtime + 2:
            raise RuntimeError(f'Compile translations before building: {po.relative_to(ROOT)}')


def prepare_resources(folder):
    environment = os.environ.copy()
    environment['GRADEBOOK_DATA_DIR'] = str(folder / 'build-data')
    environment['GRADEBOOK_STATIC_ROOT'] = str(folder / 'staticfiles')
    environment['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    environment['DJANGO_DEBUG'] = '0'
    subprocess.run([sys.executable, str(ROOT / 'manage.py'), 'check'], cwd=ROOT, env=environment, check=True)
    subprocess.run([sys.executable, str(ROOT / 'manage.py'), 'collectstatic', '--noinput', '--verbosity', '0'], cwd=ROOT, env=environment, check=True)
    environment['GRADEBOOK_BUILD_STATIC_DIR'] = environment['GRADEBOOK_STATIC_ROOT']
    return environment


def verify_bundle(folder):
    required = ['StudentGradebook.exe', '_internal/runtime/staticfiles/css/app.css',
        '_internal/templates/base.html', '_internal/locale/th/LC_MESSAGES/django.mo',
        '_internal/apps/assessments/data/marking-scheme_kpac.json',
        '_internal/apps/assessments/migrations/0012_marking_scheme_library.py',
        '_internal/apps/reports/document_templates/module-record.docx',
        '_internal/apps/reports/spreadsheet_templates/score-styles.xlsx']
    for name in required:
        if not (folder / name).is_file():
            raise RuntimeError('Required file missing from bundle: '+name)
    forbidden = {'app-data', '.git', 'others', '.venv', '.venv-build', 'backups', 'logs', 'build-data'}
    for path in folder.rglob('*'):
        relative = path.relative_to(folder)
        if any(part in forbidden or part.startswith('~$') for part in relative.parts) or path.suffix.lower() in {'.sqlite3', '.db'} or path.name == 'secret-key.txt':
            raise RuntimeError('Unexpected personal/development file in bundle: '+str(relative))


def check_executable(bundle, folder):
    result_path = folder / 'runtime-check.json'
    completed = subprocess.run([str(bundle / 'StudentGradebook.exe'), '--desktop-check', str(result_path)],
                               cwd=bundle, timeout=120)
    if not result_path.exists():
        raise RuntimeError('The built executable could not complete its startup check. No new release was published.')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if completed.returncode or not result.get('ok'):
        raise RuntimeError('Packaged startup check failed. No new release was published.\n'+result.get('error','Unknown error'))
    print('Built executable passed: '+', '.join(result['checks']))


def add_distribution_notices(bundle):
    """Keep project notices and available upstream license files with the app."""
    shutil.copy2(ROOT / 'LICENSE', bundle / 'LICENSE.txt')
    for name in ('PRIVACY.md', 'code-signing-policy.md'):
        shutil.copy2(ROOT / 'docs' / name, bundle / name)
    notices = bundle / 'THIRD-PARTY-LICENSES'
    notices.mkdir()
    shutil.copy2(ROOT / 'static/vendor/tabulator/6.6.0/LICENSE', notices / 'Tabulator-MIT.txt')
    inventory = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata['Name'].lower()):
        name = distribution.metadata['Name']
        copied = []
        for relative in distribution.files or ():
            parts = relative.parts
            if '..' in parts or relative.is_absolute():
                continue
            if not (relative.name.lower().startswith(('license', 'copying', 'notice')) or 'licenses' in parts):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                destination = notices / name / Path(*parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied.append(str(destination.relative_to(bundle)))
        inventory.append({'name': name, 'version': distribution.version, 'license_files': copied})
    for candidate in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE'):
        if candidate.is_file():
            shutil.copy2(candidate, notices / 'Python-LICENSE.txt')
            break
    (notices / 'build-environment.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not args.check_only and sys.platform != 'win32':
        parser.error('Build the Windows executable on Windows. Use --check-only for a resource review on this computer.')
    check_resources()
    if not args.check_only:
        import tkinter
        import webview
        import PyInstaller
    with tempfile.TemporaryDirectory(prefix='gradebook-build-') as temporary:
        folder = Path(temporary)
        environment = prepare_resources(folder)
        if args.check_only:
            print('Resource checks and isolated static collection passed. No executable was built.')
            return
        # Build in a temporary directory so a failed build cannot replace a prior release.
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
            '--distpath', str(folder / 'dist'), '--workpath', str(folder / 'work'),
            str(ROOT / 'packaging' / 'windows.spec')], cwd=ROOT, env=environment, check=True)
        bundle = folder / 'dist' / 'StudentGradebook'
        verify_bundle(bundle)
        check_executable(bundle, folder)
        shutil.copy2(ROOT / 'packaging' / 'WINDOWS-READ-ME.txt', bundle / 'READ-ME.txt')
        add_distribution_notices(bundle)
        destination = ROOT / 'dist' / 'StudentGradebook'
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(bundle, destination)
    archive_distribution(destination)


def archive_distribution(destination, signature=None):
    """Archive the final bundle only after any signing and runtime checks."""
    destination = Path(destination)
    archive_path = destination.parent / 'StudentGradebook-Windows.zip'
    with ZipFile(archive_path, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                archive.write(path, 'StudentGradebook/'+str(path.relative_to(destination)))
    manifest = {'file': archive_path.name, 'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}
    if signature is not None:
        manifest['signature'] = signature
    (archive_path.parent / 'StudentGradebook-Windows.sha256.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Windows folder: '+str(destination))
    print('Deliver this ZIP: '+str(archive_path))
    print('Test it on a Windows computer without Python before distributing.')
    return archive_path


if __name__ == '__main__':
    main()
