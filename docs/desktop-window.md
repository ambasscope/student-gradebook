# Embedded desktop window

The desktop edition displays the existing Django pages in a pywebview window.
It does not open Safari, Chrome, or Edge as a separate application. The desktop
window starts a loopback-only Waitress worker and waits for accepted work to
finish when closed. No Qt project or interface rewrite is needed.

## Try from source

Double-click `Start-Desktop-Mac.command` or `Start-Desktop-Windows.bat`.
The first run needs Python and internet to create `.venv-desktop` and install
`requirements-desktop.txt`; it can take several minutes. Subsequent runs reuse
that environment. These source setup scripts may show a terminal; the packaged
Windows executable runs without one.

Equivalent command:

```text
python launcher.py --desktop
```

The source desktop scripts use the same project-local `app-data` as the original
source browser edition. Save and close the browser edition before starting the
desktop edition against those records. `GRADEBOOK_DATA_DIR` overrides this path.
A test copy should use a separate data folder.

If you manage your own virtual environment:

```text
python -m pip install -r requirements-desktop.txt
python desktop_launcher.py
```

Calling `desktop_launcher.py` directly uses the packaged edition's per-user data
default, unless `GRADEBOOK_DATA_DIR` is set. That default is:

- Windows: `%LOCALAPPDATA%\StudentGradebook\data`
- macOS: `~/Library/Application Support/StudentGradebook/data`

Use the native **Student Gradebook → Data folder / โฟลเดอร์ข้อมูล** menu to
open the actual location. The original `Start-Mac.command`, `Start-Windows.bat`,
and browser development workflow remain available.

## Normal operation

- Open the application once; opening it again restores the existing desktop window.
- Import file pickers continue using the embedded browser's native file chooser.
- Word/Excel export buttons send the original POST once, then display a native
  Save dialog. Cancelling it leaves the page and existing files intact. Server
  validation errors and stale report previews are shown in the report page.
- Existing links to internal editors stay inside the desktop window.
- Unsaved score changes are checked before closing. Cancel keeps the window open.
- Closing the window, or using the native Quit action, stops its server after
  accepted save/export requests finish. There is no separate control window.
- Language switching and Tabulator still use the existing HTML/CSS/JavaScript.
  Embedded browser cookies are private to that run.

## Windows distribution

`Build-Windows.bat` now includes pywebview, its Windows .NET components, native
loader DLLs, and JavaScript assets. Build on Windows, then distribute the entire
`dist/StudentGradebook-Windows.zip`. See `windows-portable.md`.

The receiving computer needs Microsoft Edge WebView2 Runtime. Modern Windows
systems commonly have it already. If unavailable, the application explains how
to install it instead of using the old Internet Explorer engine. For an offline
computer, provide Microsoft's matching offline runtime installer separately.
The runtime is not bundled into this application's ZIP.

Reference: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

## macOS distribution

The source desktop window uses macOS WebKit through PyObjC. A double-clickable
`.app` must still be built and checked on macOS; this change does not produce a
macOS application bundle or a Windows executable from this source folder.

## Interface changes

Continue editing the Django templates, `static/css/app.css`, and existing
JavaScript files. `config/desktop_window.py` controls the window, startup page,
native menu, closing, and report-save bridge. `static/js/desktop.js` connects
report forms and internal links only when running inside pywebview.

Desktop dependencies: https://pywebview.flowrl.com/guide/installation.html
Desktop APIs: https://pywebview.flowrl.com/api/
