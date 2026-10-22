# Portability and distribution

## First delivery: portable source folder

The same Python/Django code runs on Windows and macOS. Users need a supported
Python installed and internet for initial dependency installation. The platform
launchers delegate to the same `launcher.py`; no business logic is duplicated.
The application runs on the local computer and opens in the user's browser.

The Mac launcher checks Python versions on the shell search path and common
python.org/Homebrew locations. It skips unsupported interpreters, including an
older Conda Python that may be selected by Terminal, without changing shell or
Conda settings. It prints the selected Python version before starting the app.

The environment signature includes its source folder, Python version, operating
system, machine architecture, and requirements hash. A mismatch causes the old
generated environment to be retained under another name and a new one created.
Do not intentionally distribute virtual environments across computers.

All mutable business data and installation secrets live in `app-data/`:

```text
app-data/
├── db.sqlite3
├── reports/
├── backups/
└── config/
    └── secret-key.txt
```

Stop all application processes before copying `app-data/`, including any SQLite
sidecar files that may exist. Online backups should use SQLite's backup API.
The starter reserves the backups folder; automatic backups are not implemented.
When upgrading source code, preserve `app-data/` and back it up first. Schema
migrations run on launch and must be reviewed/tested before distributing updates.

The original starter used `data/db.sqlite3` and `media/`. If you used that earlier
layout, stop it and move the database to `app-data/db.sqlite3` and retained report
files to `app-data/reports/` before starting this version. No existing data was
automatically migrated by this structural update.

## Windows delivery: no Python installation required

The Windows folder build is now prepared. See [the Windows release guide](windows-portable.md)
for the build batch file, desktop control window, per-user data, and target-platform
verification. The source edition retains the project-local data layout above.

## Other desktop releases

Once the business workflows are complete, package the Python runtime and app
into separate releases for Windows and macOS. PyInstaller is one option; it
requires builds for each target platform. Mac CPU architectures must also be
accounted for. A shared source project does not mean one executable for both OSes.

In packaged releases the executable may sit in a read-only location, so place
mutable data in a user-selected writable folder or the OS application-data
directory. The configurable data path supports that future packaging decision.
Include Django migrations, HTML/static assets, and Word templates in each build.
Signing and macOS notarization are release tasks, not included in this starter.

## One app, multiple pages

The four Django apps are internal code modules. Users see a single application
with shared navigation and no account setup or sign-in. Classrooms, Courses, Modules, and Reports
are normal page links styled as tabs, each with a stable URL. This avoids losing
an entire interface state when changing sections and does not require React.

## References

- [Python virtual environment portability](https://docs.python.org/3/library/venv.html)
- [PyInstaller platform-specific builds](https://pyinstaller.org/en/stable/operating-mode.html)
- [Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/)

## Translation catalogs

Include `locale/` in source distributions and desktop bundles. Compiled `.mo`
files allow normal users to switch English/Thai without installing gettext.
The developer editing `.po` files needs gettext to compile them. Refer to
translations.md for update and compile commands.
