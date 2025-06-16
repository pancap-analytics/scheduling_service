@echo off
echo Installing Local Scheduler Service...
set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
set SERVICE_SCRIPT=C:\SchedulerService\source\windows_service_wrapper.py

echo Removing any existing service...
"%LOCAL_PYTHON%" "%SERVICE_SCRIPT%" remove >nul 2>&1
timeout /t 2 /nobreak >nul

echo Installing service...
"%LOCAL_PYTHON%" "%SERVICE_SCRIPT%" install

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Service installed successfully!
    echo   Service Name: PythonAnalyticsSchedulerLocal
    echo   Dashboard: http://localhost:5001
) else (
    echo ERROR: Service installation failed!
)
pause
