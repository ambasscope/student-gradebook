# Student Gradebook

A local desktop gradebook for teachers, with an English/Thai interface.
It runs on Windows using pywebview, Django and SQLite. The source also supports
macOS. Teachers can work without a login and export Word and Excel reports.

## Features

- Teacher name and academic status.
- Classrooms, Excel/CSV student import and optional school-issued student IDs.
- Studying/resigned status with a resignation date; earlier scores are retained.
- Courses, teaching periods, units and modules, with copy actions for reuse.
- Reusable marking categories, subcategories and qualitative assessment rubrics.
- Sum, average and weighted-average category scores.
- Spreadsheet-style entry, paste, autofill, attendance and class comments.
- Thai module-record Word reports and A4 portrait Excel score workbooks.

## Windows app

Download a release ZIP from the [Releases page](https://github.com/ambasscope/student-gradebook/releases).
Extract the whole folder and open
`StudentGradebook.exe`, keeping `_internal` beside it. Python is bundled.
Microsoft Edge WebView2 Runtime is required. Closing the app window stops it.

The current application is **unsigned**. SignPath Foundation sponsorship is
being sought; no free signing approval or verified publisher is claimed.
See the [Code signing policy](docs/code-signing-policy.md).

## Data and updates

The Windows executable stores records at
`%LOCALAPPDATA%\StudentGradebook\data\db.sqlite3` by default. Use the native
**Student Gradebook → Data folder** menu to open the actual location.
Replacing the application folder preserves this separate data folder.
To move work between computers, close the app and copy the whole data folder
separately. Independent installations do not synchronize records.

Source launchers use the project's `app-data` folder. The source repository and
clean distribution packages contain no teacher/student database or reports.
See the [privacy information](docs/PRIVACY.md).

## Run from source

Install a supported Python version (Python 3.12 is used for Windows builds).
Double-click `Start-Desktop-Windows.bat` or `Start-Desktop-Mac.command`.
The first setup downloads dependencies and applies database migrations.
The source launchers may show a setup terminal. Normal use works locally.
The `Start-Windows.bat` and `Start-Mac.command` launchers open the browser edition.

## Reports and student status

Module Record Word reports count students currently marked Studying, including
absent and unassessed students. Missing assessments count as failed. Excel score
workbooks keep resigned students as grey rows with no displayed marks; saved
marks remain in SQLite. Score entry uses the module's teaching date to exclude
students from their resignation date onward; undated modules use today's date.

## Build and development

Build on Windows with `Build-Windows.bat` or the GitHub Actions Windows build.
Distribute the complete `dist/StudentGradebook-Windows.zip` folder edition.
See [Windows build instructions](docs/windows-portable.md),
[desktop behavior](docs/desktop-window.md) and [signing setup](docs/windows-signing.md).

Useful focused checks:

```sh
python manage.py test apps.students.tests.test_status apps.students.tests.test_status_migration config.test_deletion --noinput
python -m unittest config.test_desktop config.test_windows_build tools.tests.test_windows_signing
```

Some older tests have expectations from earlier versions and are being updated;
the focused checks above cover current student status, migration, deletion,
desktop startup and signing preparation. Real publisher signing requires an
approved signing service; mocked tests cannot replace certificate validation.

## Remove the app

Close the app and delete its application folder and any shortcuts. Personal
records remain in the separate data folder. Delete that folder only if you also
intend to erase your records; keep a backup first. A shared WebView2 installation
is managed separately by Windows.

## License

The application source is offered under the [MIT License](LICENSE).
Third-party components retain their own licenses; the bundled Tabulator license
is in `static/vendor/tabulator/6.6.0/LICENSE`. This license does not change
ownership of teachers' records, imported files, or generated reports.
