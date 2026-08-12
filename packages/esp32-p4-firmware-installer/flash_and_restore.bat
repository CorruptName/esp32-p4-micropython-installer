@echo off
setlocal
cd /d "%~dp0"

python -c "import esptool, serial" >nul 2>&1
if errorlevel 1 (
    echo Installing required Python packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

python enable_espnow.py %*
if errorlevel 1 goto :failed

echo.
echo Finished successfully.
pause
exit /b 0

:failed
echo.
echo The operation did not complete. Read README.md before retrying.
pause
exit /b 1