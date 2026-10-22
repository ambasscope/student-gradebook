# Build the Windows app with GitHub Actions

The workflow is `.github/workflows/build-windows.yml`. The project source must
be at the repository root, beside `requirements-windows-build.txt` and `tools`.
The workflow uses a Windows Server 2022 runner and 64-bit Python 3.12.

## Run a build

Push the prepared source to `codex/windows-build` to start its initial build.
Once the workflow is on the repository's default branch, you can also open
Actions → Build Windows desktop app → Run workflow and select a branch.

The job installs dependencies, runs desktop/packaging checks, creates the
PyInstaller application folder, and executes the built program's hidden startup
check. It uploads artifacts only after a successful build and startup check.
No GitHub Release is published automatically.

## Download and distribute

Open the successful run and download the `StudentGradebook-Windows` artifact.
Extract it to get `StudentGradebook-Windows.zip` and its SHA-256 manifest.
Distribute the inner `StudentGradebook-Windows.zip`. Users extract that ZIP,
keep `_internal` beside `StudentGradebook.exe`, and double-click the executable.
They need Microsoft Edge WebView2 Runtime, but not Python or a terminal.

Artifacts are retained for 14 days. Download the distribution before expiry.
The build's startup check does not replace manually testing native windows,
clipboard behavior, file import, and Word/Excel save dialogs on Windows.

## Source and data

Use the clean source package. It excludes developer databases, backups,
secrets, Python environments, and local reports. Do not upload the original
project's `app-data` or `.venv` directories. Build data is placed in the runner's
temporary directory, and only the generated ZIP and checksum are uploaded.

The build uses GitHub-hosted runner time under the repository owner's account.
Repository settings must allow GitHub Actions and the actions used by the job.

References:
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://github.com/actions/upload-artifact
