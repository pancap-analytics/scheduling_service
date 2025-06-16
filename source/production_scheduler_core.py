# SchedulerService/production_scheduler_core.py
import os
import sys
import logging
import subprocess
import threading
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from db_models import DatabaseManager, TaskManager, RunManager, HealthManager, AlertManager
from production_config import VENV_PYTHON, LOG_DIR, PROJECT_ROOT

# Configure logging with rotation
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

class ProductionScheduler:
    """Production-grade scheduler with dependency support and resilience."""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize database managers
        self.db = DatabaseManager()
        self.task_manager = TaskManager(self.db)
        self.run_manager = RunManager(self.db)
        self.health_manager = HealthManager(self.db)
        self.alert_manager = AlertManager(self.db)
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler(
            timezone="America/Chicago",
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300
            }
        )
        
        # Thread pool for parallel execution
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Track running processes
        self.running_processes = {}
        self.process_lock = threading.Lock()
        
        # Health monitoring
        self.start_health_monitor()
        
        self.logger.info("Production scheduler initialized")
    
    def setup_logging(self):
        """Configure production logging with rotation."""
        log_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Main log file with size rotation
        main_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, 'scheduler_service.log'),
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        main_handler.setFormatter(log_formatter)
        root_logger.addHandler(main_handler)
        
        # Error log file
        error_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, 'scheduler_errors.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_formatter)
        root_logger.addHandler(error_handler)
        
        # Daily log file
        daily_handler = TimedRotatingFileHandler(
            os.path.join(LOG_DIR, 'scheduler_daily.log'),
            when='midnight',
            interval=1,
            backupCount=30
        )
        daily_handler.setFormatter(log_formatter)
        root_logger.addHandler(daily_handler)
    
    def start_health_monitor(self):
        """Start background health monitoring."""
        def monitor_health():
            while True:
                try:
                    # Collect metrics
                    metrics = {
                        'cpu_percent': psutil.cpu_percent(interval=1),
                        'memory_percent': psutil.virtual_memory().percent,
                        'disk_usage': psutil.disk_usage('/').percent,
                        'running_tasks': len(self.running_processes),
                        'scheduled_jobs': len(self.scheduler.get_jobs()),
                        'python_version': sys.version,
                        'scheduler_running': self.scheduler.running
                    }
                    
                    # Determine health status
                    status = 'healthy'
                    if metrics['cpu_percent'] > 90 or metrics['memory_percent'] > 90:
                        status = 'warning'
                    if metrics['disk_usage'] > 95:
                        status = 'critical'
                    
                    # Update heartbeat
                    self.health_manager.update_heartbeat(status, metrics)
                    
                except Exception as e:
                    self.logger.error(f"Health monitor error: {e}")
                
                time.sleep(30)  # Update every 30 seconds
        
        health_thread = threading.Thread(target=monitor_health, daemon=True)
        health_thread.start()
    
    def load_tasks_from_db(self):
        """Load and schedule all active tasks from database."""
        try:
            tasks = self.task_manager.get_active_tasks()
            
            for task in tasks:
                if task.get('schedule_type') and task.get('schedule_config'):
                    self.schedule_task(task)
                else:
                    self.logger.warning(f"Task {task['task_name']} has no schedule defined")
            
            self.logger.info(f"Loaded {len(tasks)} tasks from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load tasks: {e}")
            self.alert_manager.create_alert(
                'scheduler_error', 'critical', 
                f"Failed to load tasks from database: {e}"
            )
    
    def schedule_task(self, task: Dict):
        """Schedule a task based on its configuration."""
        try:
            task_id = task['task_id']
            task_name = task['task_name']
            schedule_config = task['schedule_config']
            
            # Create trigger based on schedule type
            if task['schedule_type'] == 'cron':
                trigger = CronTrigger(**schedule_config)
            elif task['schedule_type'] == 'interval':
                trigger = IntervalTrigger(**schedule_config)
            else:
                self.logger.error(f"Unknown schedule type: {task['schedule_type']}")
                return
            
            # Add job to scheduler
            job = self.scheduler.add_job(
                self.execute_task_with_dependencies,
                trigger=trigger,
                args=[task_id],
                id=f"task_{task_id}",
                name=task_name,
                replace_existing=True
            )
            
            self.logger.info(f"Scheduled task: {task_name} (ID: {task_id})")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule task {task_name}: {e}")
            self.alert_manager.create_alert(
                'schedule_error', 'error',
                f"Failed to schedule task {task_name}: {e}",
                task_id=task_id
            )
    
    def execute_task_with_dependencies(self, task_id: int):
        """Execute a task after checking dependencies."""
        task = self.task_manager.get_task(task_id=task_id)
        if not task:
            self.logger.error(f"Task {task_id} not found")
            return
        
        try:
            # Check dependencies
            if not self.run_manager.check_dependencies_satisfied(task_id):
                self.logger.info(f"Dependencies not satisfied for task {task['task_name']}")
                
                # Create a skipped run entry
                run_id = self.run_manager.create_run(task_id, triggered_by='schedule')
                self.run_manager.update_run_status(run_id, 'skipped', 
                    error_message='Dependencies not satisfied')
                
                self.alert_manager.create_alert(
                    'dependency_not_met', 'warning',
                    f"Task {task['task_name']} skipped due to unmet dependencies",
                    task_id=task_id
                )
                return
            
            # Execute the task
            self.execute_task(task_id)
            
        except Exception as e:
            self.logger.error(f"Error executing task {task_id}: {e}")
            self.alert_manager.create_alert(
                'task_error', 'error',
                f"Error executing task {task['task_name']}: {e}",
                task_id=task_id
            )
    
    def execute_task(self, task_id: int, retry_count: int = 0):
        """Execute a single task with retry logic."""
        task = self.task_manager.get_task(task_id=task_id)
        if not task:
            return
        
        # Create run record
        run_id = self.run_manager.create_run(
            task_id, 
            triggered_by='retry' if retry_count > 0 else 'schedule',
            process_id=os.getpid()
        )
        
        # Update status to running
        self.run_manager.update_run_status(run_id, 'running')
        
        # Prepare execution
        script_path = task['script_path']
        task_name = task['task_name']
        timeout = task.get('timeout_seconds', 3600)
        
        # Create log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_dir = os.path.join(os.path.dirname(script_path), f"{task_name}_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{task_name}_{timestamp}.log")
        
        self.logger.info(f"Executing task {task_name} (Run ID: {run_id})")
        
        try:
            # Create clean environment
            clean_env = self.create_clean_environment()
            
            # Execute script
            with open(log_file, 'w') as flog:
                flog.write(f"=== Task Execution: {task_name} ===\n")
                flog.write(f"Run ID: {run_id}\n")
                flog.write(f"Started: {datetime.now()}\n")
                flog.write(f"Script: {script_path}\n")
                flog.write(f"Python: {VENV_PYTHON}\n")
                flog.write("="*50 + "\n\n")
                flog.flush()
                
                # Use cmd wrapper for Windows
                if sys.platform == 'win32':
                    cmd = f'cmd.exe /c ""{VENV_PYTHON}" "{script_path}""'
                    process = subprocess.Popen(
                        cmd,
                        stdout=flog,
                        stderr=subprocess.STDOUT,
                        cwd=os.path.dirname(script_path),
                        env=clean_env,
                        shell=True
                    )
                else:
                    process = subprocess.Popen(
                        [VENV_PYTHON, script_path],
                        stdout=flog,
                        stderr=subprocess.STDOUT,
                        cwd=os.path.dirname(script_path),
                        env=clean_env
                    )
                
                # Track process
                with self.process_lock:
                    self.running_processes[run_id] = process
                
                # Wait with timeout
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    self.logger.error(f"Task {task_name} timed out after {timeout} seconds")
                    process.terminate()
                    time.sleep(5)
                    if process.poll() is None:
                        process.kill()
                    
                    self.run_manager.update_run_status(
                        run_id, 'timeout', 
                        error_message=f'Timed out after {timeout} seconds',
                        log_file_path=log_file
                    )
                    
                    self.alert_manager.create_alert(
                        'task_timeout', 'error',
                        f"Task {task_name} timed out after {timeout} seconds",
                        task_id=task_id, run_id=run_id
                    )
                    return
                finally:
                    with self.process_lock:
                        self.running_processes.pop(run_id, None)
            
            # Check exit code
            if exit_code == 0:
                self.logger.info(f"Task {task_name} completed successfully")
                self.run_manager.update_run_status(
                    run_id, 'success', 
                    exit_code=exit_code,
                    log_file_path=log_file
                )
            else:
                error_msg = f"Task {task_name} failed with exit code {exit_code}"
                self.logger.error(error_msg)
                
                # Update run status
                self.run_manager.update_run_status(
                    run_id, 'failed',
                    exit_code=exit_code,
                    error_message=error_msg,
                    log_file_path=log_file
                )
                
                # Handle retry
                if retry_count < task.get('max_retries', 3):
                    retry_delay = task.get('retry_delay_seconds', 300)
                    self.logger.info(f"Retrying task {task_name} in {retry_delay} seconds")
                    
                    # Schedule retry
                    self.scheduler.add_job(
                        self.execute_task,
                        'date',
                        run_date=datetime.now() + timedelta(seconds=retry_delay),
                        args=[task_id, retry_count + 1],
                        id=f"retry_{task_id}_{retry_count}",
                        replace_existing=True
                    )
                else:
                    # Max retries reached
                    self.alert_manager.create_alert(
                        'task_failed', 'error',
                        f"Task {task_name} failed after {retry_count} retries",
                        task_id=task_id, run_id=run_id
                    )
        
        except Exception as e:
            error_msg = f"Exception executing task {task_name}: {e}"
            self.logger.exception(error_msg)
            
            self.run_manager.update_run_status(
                run_id, 'failed',
                error_message=str(e),
                log_file_path=log_file
            )
            
            self.alert_manager.create_alert(
                'task_exception', 'critical',
                error_msg,
                task_id=task_id, run_id=run_id,
                details={'exception': str(e), 'type': type(e).__name__}
            )
    
    def create_clean_environment(self) -> Dict[str, str]:
        """Create a clean environment for subprocess execution."""
        clean_env = {
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', 'C:\\Windows'),
            'PATH': 'C:\\Windows\\system32;C:\\Windows',
            'TEMP': os.environ.get('TEMP', 'C:\\Temp'),
            'TMP': os.environ.get('TMP', 'C:\\Temp'),
        }
        return clean_env
    
    def start(self):
        """Start the scheduler."""
        try:
            # Load tasks from database
            self.load_tasks_from_db()
            
            # Add listener
            self.scheduler.add_listener(
                self.job_executed_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
            
            # Start scheduler
            self.scheduler.start()
            self.logger.info("Scheduler started successfully")
            
            # Keep running
            while True:
                time.sleep(60)
                # Periodic cleanup
                self.cleanup_old_runs()
                
        except KeyboardInterrupt:
            self.logger.info("Scheduler interrupted by user")
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")
            self.alert_manager.create_alert(
                'scheduler_crash', 'critical',
                f"Scheduler crashed: {e}"
            )
        finally:
            self.shutdown()
    
    def job_executed_listener(self, event):
        """Handle job execution events."""
        if event.exception:
            self.logger.error(f"Job {event.job_id} crashed: {event.exception}")
        else:
            self.logger.debug(f"Job {event.job_id} executed successfully")
    
    def cleanup_old_runs(self):
        """Clean up old run records and logs."""
        try:
            # This would be implemented based on retention policy
            pass
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def shutdown(self):
        """Gracefully shutdown the scheduler."""
        self.logger.info("Shutting down scheduler...")
        
        # Stop scheduler
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
        
        # Terminate running processes
        with self.process_lock:
            for run_id, process in self.running_processes.items():
                try:
                    process.terminate()
                    self.logger.info(f"Terminated process for run {run_id}")
                except:
                    pass
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Update health status
        self.health_manager.update_heartbeat('offline')
        
        self.logger.info("Scheduler shutdown complete")

if __name__ == '__main__':
    scheduler = ProductionScheduler()
    scheduler.start()