@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Install Python 3.12 for Windows from python.org, including the Python launcher and Tcl/Tk.
    pause
    exit /b 1
)
if not exist ".venv-build\Scripts\python.exe" (
    py -3.12 -m venv .venv-build
    if errorlevel 1 goto failed
)
".venv-build\Scripts\python.exe" -m pip install -r requirements-windows-build.txt
if errorlevel 1 goto failed
".venv-build\Scripts\python.exe" tools\build_windows.py
if errorlevel 1 goto failed
echo.
echo Build complete. Open dist\StudentGradebook\StudentGradebook.exe to test it.
echo Deliver dist\StudentGradebook-Windows.zip and keep the entire extracted folder together.
pause
exit /b 0
:failed
echo.
echo The build failed. Review the message above. Your student database was not used for this build.
pause
exit /b 1
