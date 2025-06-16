@echo off
REM test_installation_fixed.bat
REM Fixed test script that uses a separate Python file

echo Testing Local Scheduler Installation...
echo.

set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
set SOURCE_DIR=C:\SchedulerService\source

echo Configuration:
echo   Python: %LOCAL_PYTHON%
echo   Source: %SOURCE_DIR%
echo.

REM Check if Python exists
if not exist "%LOCAL_PYTHON%" (
    echo ERROR: Local Python not found at %LOCAL_PYTHON%
    goto :error
)

REM Check if source directory exists
if not exist "%SOURCE_DIR%" (
    echo ERROR: Source directory not found at %SOURCE_DIR%
    goto :error
)

REM Change to source directory and run test
cd /d "%SOURCE_DIR%"

REM Run the Python test script
"%LOCAL_PYTHON%" test_installation.py

goto :end

:error
echo.
echo Test cannot run due to missing files.
echo Please check the installation.

:end
echo.
pause