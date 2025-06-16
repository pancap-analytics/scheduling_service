# production_config_local.py
"""
Local Production Configuration for Python Analytics Scheduler
"""

import os

# Paths
LOCAL_ROOT = r"C:\SchedulerService"
PROJECT_ROOT = r"\\PANCAPDC1\Pan\Public\Nick\Python\Analytics_Library"
VENV_PYTHON = r"C:\SchedulerService\venv\Scripts\python.exe"

# Logs
LOG_DIR = os.path.join(LOCAL_ROOT, "logs")
SCHEDULER_LOG_FILE = os.path.join(LOG_DIR, "scheduler_service.log")

# Database configuration (unchanged)
DATABASE_CONFIG = {
    'host': '10.0.10.126',
    'port': 5432,
    'database': 'coder',
    'user': 'postgres',
    'password': 'Postgres'
}

DATABASE_SCHEMA = 'nicks_workspace'

# Dashboard configuration
DASHBOARD_CONFIG = {
    'host': '0.0.0.0',  # Listen on all interfaces for network access
    'port': 5001,
    'debug': False
}

# Service configuration
SERVICE_CONFIG = {
    'name': 'PythonAnalyticsSchedulerLocal',
    'display_name': 'Python Analytics Scheduler (Local)',
    'description': 'Local Python Analytics Scheduler with Dashboard'
}

# Scheduler configuration
SCHEDULER_CONFIG = {
    'timezone': 'America/Chicago',
    'max_worker_threads': 10,
    'job_defaults': {
        'coalesce': True,
        'max_instances': 1,
        'misfire_grace_time': 300
    }
}

# Task defaults
TASK_DEFAULTS = {
    'max_retries': 3,
    'retry_delay_seconds': 300,
    'timeout_seconds': 3600
}

# Alert configuration
ALERT_CONFIG = {
    'email_enabled': False,
    'email_smtp_server': 'smtp.example.com',
    'email_smtp_port': 587,
    'email_username': 'scheduler@example.com',
    'email_password': 'password',
    'email_from': 'scheduler@example.com',
    'email_to': ['admin@example.com'],
    'email_subject_prefix': '[Scheduler Alert]'
}

# Retention policy
RETENTION_POLICY = {
    'keep_successful_runs_days': 30,
    'keep_failed_runs_days': 90,
    'keep_logs_days': 30,
    'cleanup_interval_hours': 24
}

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)