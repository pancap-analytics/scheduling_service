@echo off
echo Task Management CLI
echo.
set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
cd /d "C:\SchedulerService\source"

if "%1"=="" (
    echo Usage: manage_tasks.bat [command] [arguments]
    echo.
    echo Examples:
    echo   manage_tasks.bat list
    echo   manage_tasks.bat create "Task_Name" "\\path\to\script.py"
    echo.
    goto :end
)

"%LOCAL_PYTHON%" task_management_cli.py %*

:end
pause
