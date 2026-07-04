@echo off
REM ============================================================
REM  IBM Daily Email Digest - daily runner (called by Task Scheduler)
REM  Activates the project venv (if present) and runs the pipeline.
REM ============================================================
setlocal

REM Project root = parent of this scripts\ folder
set "ROOT=%~dp0.."
cd /d "%ROOT%"

REM Use the venv Python if it exists, else fall back to system Python
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PY=%ROOT%\.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

REM Log each run (rotating by date) into output\logs
if not exist "%ROOT%\output\logs" mkdir "%ROOT%\output\logs"
set "LOG=%ROOT%\output\logs\run_%date:~-4%-%date:~4,2%-%date:~7,2%.log"

echo ==== Run started %date% %time% ==== >> "%LOG%"
"%PY%" -m src.main >> "%LOG%" 2>&1
echo ==== Run finished %date% %time% (exit %errorlevel%) ==== >> "%LOG%"

endlocal
