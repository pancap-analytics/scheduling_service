@echo off
echo Running Scheduler in Debug Mode...
echo Press Ctrl+C to stop
echo.
set LOCAL_PYTHON=C:\SchedulerService\venv\Scripts\python.exe
cd /d "C:\SchedulerService\source"
"%LOCAL_PYTHON%" local_scheduler_service.py
pause
