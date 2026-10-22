# Windows folder release

This build produces a folder containing `StudentGradebook.exe` and `_internal/`.
Users extract the complete folder and double-click the executable. Python and
app libraries are bundled. The app opens its existing interface inside one
pywebview desktop window. Closing that window stops its background server;
no separate browser, control window, terminal, or Ctrl+C is needed.
Microsoft Edge WebView2 Runtime must be installed on the receiving computer.

## Build on Windows

Windows executables must be built on Windows with the matching Python/platform
architecture. Use a Windows computer or a Windows virtual machine for this step.
The build scripts can be prepared on macOS, but do not cross-compile an `.exe`.

1. Copy a clean project folder to Windows. Exclude the developer `.venv`,
   `app-data`, `runtime`, `dist`, and `others` folders. The supplied clean source
   ZIP already excludes personal data.
2. Install Python 3.12 from python.org with the Python launcher and Tcl/Tk
   components, and Microsoft Edge WebView2 Runtime. Internet is needed on the build computer to install dependencies.
3. Double-click `Build-Windows.bat`. It creates `.venv-build`, installs the
   application and PyInstaller dependencies, collects assets into an isolated
   temporary folder, and builds the release. The build uses a temporary empty
   data directory, never the developer's student database. Before publishing the
   ZIP it also runs the built executable in a hidden self-check mode, exercising
   middleware and pywebview Windows imports, a fresh database, templates, and static assets. A failing
   check stops the build without replacing the previous release.
4. Open `dist/StudentGradebook/StudentGradebook.exe` on Windows and complete the
   checks below. Keep its `_internal` folder beside it.
5. Distribute `dist/StudentGradebook-Windows.zip`. The ZIP contains the whole
   runnable folder. Do not distribute only the `.exe`.

The developer build uses a terminal window to show progress; the delivered
application does not. A subsequent rebuild uses the same batch file. The source
launchers (`Start-Windows.bat`, `Start-Mac.command`) retain their existing behavior.

If you prefer commands after installing the build dependencies:

```bat
py -3.12 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements-windows-build.txt
.venv-build\Scripts\python.exe tools\build_windows.py
```

On any development platform, an isolated resource check can run without
PyInstaller or an executable build:

```text
python tools/build_windows.py --check-only
```

Thai translations must already be compiled. If `.po` files were edited after
their `.mo` files, compile them before building. See `docs/translations.md`.

If an older executable reports `No module named whitenoise`, rebuild from the
updated source with `Build-Windows.bat` and replace the complete application
folder. Installing a Python package on the receiving computer does not add it
to an already frozen executable. The current specification explicitly includes
WhiteNoise and the middleware/template backends named in Django settings.

## Data and updates

The Windows release creates fresh user data on first launch at:

```text
%LOCALAPPDATA%\StudentGradebook\data\
    db.sqlite3
    reports\
    backups\
    config\secret-key.txt
    logs\
```

Only definitions such as the KPAC starter library are seeded. No teacher,
student, classroom, course, or score records from the build computer are shipped.
The **Student Gradebook → Data folder** menu action opens the actual configured location. An explicit
`GRADEBOOK_DATA_DIR` environment variable can select another data folder.
Relative overrides resolve beside the executable in a frozen release.

Replacing or moving the executable folder does not move or erase personal data.
To move records to another computer, quit the app and copy the complete data
folder separately. The original source edition still defaults to project-local
`app-data`; the desktop edition does not silently import or modify that database.

When an existing desktop database needs schema migrations, startup makes an
online SQLite backup in `backups` before applying them. Normal launches with no
pending migrations do not create redundant migration backups. Word/Excel exports use a native Save dialog; choose their destination. Static assets and report templates
come from the application bundle; edit source templates before rebuilding.

## Startup and closing

The desktop window launches one background worker from the bundled executable.
Waitress listens only on `127.0.0.1`, using an available port selected by the OS.
Each data directory has an OS-backed instance lock. Opening the executable again
restores the existing desktop window instead of starting another server for the same data.

Quit signals the worker and waits for accepted tasks to finish before exiting.
No terminal or Ctrl+C is needed. Unsaved score edits are checked before closing.
If the window process crashes, the worker detects its parent's exit and stops.
Startup errors appear in the desktop window or a native dialog, with rotating logs in the data folder.
Lifecycle communication uses files because a windowed Windows executable may
have no stdin/stdout/stderr streams.

## Verify before distributing

Test the actual release on a Windows computer without Python installed:

- Extract a path containing spaces and Thai characters and launch by double-click.
- Open the app again and verify only one desktop window/server uses its data.
- Import a student list, save module scores, and export Word and Excel reports.
- Switch Thai/English and check the offline static grid and marking presets.
- Save, quit with the menu, relaunch, and confirm the records persist.
- Close with the window's X and confirm its local URL stops responding.
- Replace the application folder with a rebuilt release and confirm data persists.

Resource checks and mocked lifecycle checks on macOS do not establish that a
Windows build works. The `.exe`, Windows native lock/parent-process APIs,
WebView2 and pythonnet packaging, and console-free launch still require this Windows validation.

## WebView2 and native save dialogs

Install Microsoft's WebView2 Runtime on build and receiving computers. It is
required even though no external browser window opens. For offline recipients,
provide Microsoft's standalone runtime installer separately; this ZIP does not
include the runtime. The app refuses an old Internet Explorer fallback.

Report exports use `static/js/desktop.js` and the native save bridge to preserve
POST selections and report wording on both macOS and Windows. Test export,
cancellation, and server-side validation in the actual Windows release.

For source desktop launchers and UI editing, see `desktop-window.md`.

References:

- https://pywebview.flowrl.com/guide/installation.html
- https://developer.microsoft.com/en-us/microsoft-edge/webview2/

- https://pyinstaller.org/en/stable/operating-mode.html
- https://pyinstaller.org/en/stable/spec-files.html
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
