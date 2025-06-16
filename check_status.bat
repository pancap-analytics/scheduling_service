@echo off
echo Checking Local Scheduler Service Status...
echo.

sc query "PythonAnalyticsSchedulerLocal" >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo Service is installed.
    echo.
    sc query "PythonAnalyticsSchedulerLocal"
    
    echo.
    echo Dashboard should be available at:
    echo   http://localhost:5001
    echo   http://YOUR_IP:5001 (for network access)
    
    echo.
    echo Service logs location:
    echo   C:\SchedulerService\logs\
    
) else (
    echo Service is not installed.
    echo.
    echo To install the service:
    echo   install_service.bat
)

echo.
pause
