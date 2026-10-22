"""Create a machine-local environment and launch the portable application."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv"
STAMP = ENV / ".gradebook-environment.json"

def signature(desktop=False):
    result = {
        "folder": str(ROOT),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": list(sys.version_info[:3]),
        "requirements": hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest(),
    }
    if desktop:
        result['desktop_requirements'] = hashlib.sha256((ROOT / 'requirements-desktop.txt').read_bytes()).hexdigest()
    return result

def environment_python(desktop=False):
    environment = ROOT / '.venv-desktop' if desktop else ENV
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def prepare_environment(desktop=False):
    environment = ROOT / '.venv-desktop' if desktop else ENV
    stamp = environment / '.gradebook-environment.json'
    expected = signature(desktop)
    try:
        recorded = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = None
    if recorded == expected and environment_python(desktop).exists():
        return
    if environment.exists():
        # Recreate a copied/moved environment; keep the old one recoverable.
        environment.rename(ROOT / f"{environment.name}.previous-{time.time_ns()}")
    print("Preparing this computer. Internet is needed for the first setup.", flush=True)
    venv.EnvBuilder(with_pip=True).create(environment)
    requirements = 'requirements-desktop.txt' if desktop else 'requirements.txt'
    subprocess.run([str(environment_python(desktop)), "-m", "pip", "install", "-r", str(ROOT / requirements)], cwd=ROOT, check=True)
    stamp.write_text(json.dumps(expected), encoding="utf-8")

def serve(port, open_browser):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from waitress import create_server
    call_command("check")
    call_command("migrate", interactive=False, verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0)
    url = f"http://127.0.0.1:{port}/"
    # Construct the application after collecting static files.
    server = create_server(get_wsgi_application(), host="127.0.0.1", port=port)
    print(f"Student Gradebook: {url}\nKeep this window open. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        timer = threading.Timer(0.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.run()
    finally:
        server.close()

def main():
    parser = argparse.ArgumentParser(description="Start Student Gradebook on this computer.")
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument('--desktop', action='store_true', help='Open the app in its own desktop window.')
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.desktop and (args.run or args.no_browser):
        parser.error('--desktop cannot be combined with --run or --no-browser.')
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    if not (3, 10) <= sys.version_info[:2] <= (3, 14):
        parser.error("Install Python 3.10–3.14; Python 3.12 is a suitable choice.")
    os.chdir(ROOT)
    if args.run:
        serve(args.port, not args.no_browser)
        return
    prepare_environment(args.desktop)
    if args.setup_only:
        print("Setup complete. Run the Start launcher when ready.")
        return
    if args.desktop:
        environment = os.environ.copy()
        # Source desktop mode uses the same records as the source browser app.
        # The packaged executable keeps its separate per-user default location.
        environment.setdefault('GRADEBOOK_DATA_DIR', str(ROOT / 'app-data'))
        subprocess.run([str(environment_python(True)), str(ROOT / 'desktop_launcher.py')],
                       cwd=ROOT, env=environment, check=True)
        return
    command = [str(environment_python()), str(ROOT / "launcher.py"), "--run", "--port", str(args.port)]
    if args.no_browser:
        command.append("--no-browser")
    subprocess.run(command, cwd=ROOT, check=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Could not start: {error}", file=sys.stderr)
        sys.exit(1)
