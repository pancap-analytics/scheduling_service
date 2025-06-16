@echo off
echo Starting Local Scheduler Service...
set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
set SERVICE_SCRIPT=C:\SchedulerService\source\windows_service_wrapper.py

"%LOCAL_PYTHON%" "%SERVICE_SCRIPT%" start

if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Service start command sent!
    timeout /t 5 /nobreak >nul
    sc query "PythonAnalyticsSchedulerLocal" | findstr "STATE"
    echo.
    echo Dashboard: http://localhost:5001
) else (
    echo ERROR: Failed to start service!
)
pause
