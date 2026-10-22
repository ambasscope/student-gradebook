@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 launcher.py --desktop %*
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3.10-3.14 from python.org, then start again.
        pause
        exit /b 1
    )
    python launcher.py --desktop %*
)
if errorlevel 1 (
    pause
    exit /b 1
)
endlocal
