# production_config.py
# Configuration for the Local Scheduler Service

import os

# Database Configuration
DB_CONFIG = {
    'host': '10.0.10.126',
    'port': 5432,
    'database': 'coder',
    'user': 'your_username',  # Update this
    'password': 'your_password'  # Update this
}

# Service Configuration
SERVICE_CONFIG = {
    'name': 'PythonAnalyticsSchedulerLocal',
    'display_name': 'Python Analytics Scheduler (Local)',
    'description': 'Local task scheduler for Python analytics scripts',
    'auto_start': True
}

# Web Dashboard Configuration
DASHBOARD_CONFIG = {
    'host': '0.0.0.0',
    'port': 5001,
    'debug': False
}

# Scheduler Configuration
SCHEDULER_CONFIG = {
    'timezone': 'America/New_York',  # Update to your timezone
    'job_defaults': {
        'coalesce': False,
        'max_instances': 3,
        'misfire_grace_time': 30
    }
}

# Logging Configuration
LOG_CONFIG = {
    'log_dir': r'C:\SchedulerService\logs',
    'log_level': 'INFO',
    'max_bytes': 10485760,  # 10MB
    'backup_count': 5
}

# Ensure log directory exists
os.makedirs(LOG_CONFIG['log_dir'], exist_ok=True)