@echo off
echo Stopping Local Scheduler Service...
set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
set SERVICE_SCRIPT=C:\SchedulerService\source\windows_service_wrapper.py

"%LOCAL_PYTHON%" "%SERVICE_SCRIPT%" stop

if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Service stop command sent!
    timeout /t 3 /nobreak >nul
    sc query "PythonAnalyticsSchedulerLocal" | findstr "STATE"
) else (
    echo ERROR: Failed to stop service!
)
pause
