# SchedulerService/task_management_cli.py
"""
Command-line interface for managing scheduler tasks.
Provides easy task creation, modification, and monitoring.
"""

import argparse
import sys
import json
from datetime import datetime
from tabulate import tabulate

from db_models import DatabaseManager, TaskManager, RunManager, AlertManager

class TaskManagementCLI:
    def __init__(self):
        self.db = DatabaseManager()
        self.task_mgr = TaskManager(self.db)
        self.run_mgr = RunManager(self.db)
        self.alert_mgr = AlertManager(self.db)
    
    def list_tasks(self, active_only=False):
        """List all tasks."""
        tasks = self.task_mgr.get_active_tasks() if active_only else self.db.execute_query(
            f"SELECT * FROM {self.db.schema}.scheduler_tasks ORDER BY task_name"
        )
        
        if not tasks:
            print("No tasks found.")
            return
        
        # Format for display
        headers = ['ID', 'Name', 'Script Path', 'Active', 'Max Retries', 'Timeout']
        rows = []
        
        for task in tasks:
            rows.append([
                task['task_id'],
                task['task_name'],
                task['script_path'][:50] + '...' if len(task['script_path']) > 50 else task['script_path'],
                '✓' if task['is_active'] else '✗',
                task['max_retries'],
                f"{task['timeout_seconds']}s"
            ])
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
    
    def show_task(self, task_id):
        """Show detailed task information."""
        task = self.task_mgr.get_task(task_id=task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        
        print(f"\n=== Task Details ===")
        print(f"ID: {task['task_id']}")
        print(f"Name: {task['task_name']}")
        print(f"Script: {task['script_path']}")
        print(f"Description: {task['description'] or 'N/A'}")
        print(f"Active: {'Yes' if task['is_active'] else 'No'}")
        print(f"Max Retries: {task['max_retries']}")
        print(f"Retry Delay: {task['retry_delay_seconds']}s")
        print(f"Timeout: {task['timeout_seconds']}s")
        print(f"Created: {task['created_at']}")
        print(f"Updated: {task['updated_at']}")
        
        # Show schedules
        schedules = self.db.execute_query(
            f"SELECT * FROM {self.db.schema}.task_schedules WHERE task_id = %s",
            (task_id,)
        )
        
        if schedules:
            print(f"\n=== Schedules ===")
            for sched in schedules:
                print(f"- Type: {sched['schedule_type']}")
                print(f"  Config: {json.dumps(sched['schedule_config'], indent=2)}")
                print(f"  Active: {'Yes' if sched['is_active'] else 'No'}")
        
        # Show dependencies
        deps = self.task_mgr.get_dependencies(task_id)
        if deps:
            print(f"\n=== Dependencies ===")
            for dep in deps:
                print(f"- Depends on: {dep['depends_on_task_name']} ({dep['dependency_type']})")
        
        # Show recent runs
        recent_runs = self.run_mgr.get_recent_runs(task_id=task_id, limit=5)
        if recent_runs:
            print(f"\n=== Recent Runs ===")
            headers = ['Run ID', 'Status', 'Started', 'Duration', 'Exit Code']
            rows = []
            
            for run in recent_runs:
                duration = f"{run['duration_seconds']:.1f}s" if run['duration_seconds'] else 'N/A'
                rows.append([
                    run['run_id'],
                    run['status'],
                    run['started_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    duration,
                    run['exit_code'] or 'N/A'
                ])
            
            print(tabulate(rows, headers=headers, tablefmt='simple'))
    
    def create_task(self, name, script, description=None, max_retries=3, timeout=3600):
        """Create a new task."""
        try:
            task_id = self.task_mgr.create_task(
                task_name=name,
                script_path=script,
                description=description,
                max_retries=max_retries,
                timeout_seconds=timeout
            )
            print(f"✓ Task created successfully with ID: {task_id}")
            return task_id
        except Exception as e:
            print(f"✗ Failed to create task: {e}")
            return None
    
    def add_schedule(self, task_id, schedule_type, schedule_config):
        """Add a schedule to a task."""
        try:
            # Parse schedule config if it's a string
            if isinstance(schedule_config, str):
                schedule_config = json.loads(schedule_config)
            
            schedule_id = self.task_mgr.add_schedule(task_id, schedule_type, schedule_config)
            print(f"✓ Schedule added successfully with ID: {schedule_id}")
            return schedule_id
        except Exception as e:
            print(f"✗ Failed to add schedule: {e}")
            return None
    
    def add_dependency(self, task_id, depends_on, dep_type='success'):
        """Add a dependency to a task."""
        try:
            # Get depends_on task ID if name is provided
            if not str(depends_on).isdigit():
                dep_task = self.task_mgr.get_task(task_name=depends_on)
                if not dep_task:
                    print(f"✗ Task '{depends_on}' not found")
                    return False
                depends_on = dep_task['task_id']
            
            success = self.task_mgr.add_dependency(task_id, int(depends_on), dep_type)
            if success:
                print(f"✓ Dependency added successfully")
            return success
        except Exception as e:
            print(f"✗ Failed to add dependency: {e}")
            return False
    
    def toggle_task(self, task_id):
        """Enable/disable a task."""
        task = self.task_mgr.get_task(task_id=task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        
        new_status = not task['is_active']
        success = self.task_mgr.update_task(task_id, is_active=new_status)
        
        if success:
            status_text = "enabled" if new_status else "disabled"
            print(f"✓ Task {task['task_name']} {status_text}")
        else:
            print(f"✗ Failed to update task status")
    
    def show_runs(self, task_id=None, limit=20):
        """Show recent task runs."""
        runs = self.run_mgr.get_recent_runs(task_id=task_id, limit=limit)
        
        if not runs:
            print("No runs found.")
            return
        
        headers = ['Run ID', 'Task', 'Status', 'Started', 'Duration', 'Triggered By']
        rows = []
        
        for run in runs:
            duration = f"{run['duration_seconds']:.1f}s" if run['duration_seconds'] else 'Running'
            rows.append([
                run['run_id'],
                run['task_name'][:30],
                run['status'],
                run['started_at'].strftime('%Y-%m-%d %H:%M:%S'),
                duration,
                run['triggered_by']
            ])
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
    
    def show_alerts(self, unack_only=True):
        """Show alerts."""
        if unack_only:
            alerts = self.alert_mgr.get_unacknowledged_alerts()
        else:
            alerts = self.db.execute_query(
                f"SELECT * FROM {self.db.schema}.scheduler_alerts ORDER BY created_at DESC LIMIT 50"
            )
        
        if not alerts:
            print("No alerts found.")
            return
        
        headers = ['ID', 'Type', 'Severity', 'Message', 'Created', 'Ack']
        rows = []
        
        for alert in alerts:
            rows.append([
                alert['alert_id'],
                alert['alert_type'][:20],
                alert['severity'],
                alert['message'][:50] + '...' if len(alert['message']) > 50 else alert['message'],
                alert['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                '✓' if alert.get('acknowledged', False) else '✗'
            ])
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
    
    def acknowledge_alert(self, alert_id, user='cli_user'):
        """Acknowledge an alert."""
        success = self.alert_mgr.acknowledge_alert(alert_id, user)
        if success:
            print(f"✓ Alert {alert_id} acknowledged")
        else:
            print(f"✗ Failed to acknowledge alert {alert_id}")

def main():
    parser = argparse.ArgumentParser(description='Scheduler Task Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--active', action='store_true', help='Show only active tasks')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show task details')
    show_parser.add_argument('task_id', type=int, help='Task ID')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new task')
    create_parser.add_argument('name', help='Task name')
    create_parser.add_argument('script', help='Script path')
    create_parser.add_argument('--description', help='Task description')
    create_parser.add_argument('--max-retries', type=int, default=3, help='Max retry attempts')
    create_parser.add_argument('--timeout', type=int, default=3600, help='Timeout in seconds')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Add schedule to task')
    schedule_parser.add_argument('task_id', type=int, help='Task ID')
    schedule_parser.add_argument('type', choices=['cron', 'interval'], help='Schedule type')
    schedule_parser.add_argument('config', help='Schedule config as JSON')
    
    # Dependency command
    dep_parser = subparsers.add_parser('depend', help='Add dependency to task')
    dep_parser.add_argument('task_id', type=int, help='Task ID')
    dep_parser.add_argument('depends_on', help='Depends on task ID or name')
    dep_parser.add_argument('--type', choices=['success', 'completion', 'failure'], 
                           default='success', help='Dependency type')
    
    # Toggle command
    toggle_parser = subparsers.add_parser('toggle', help='Enable/disable task')
    toggle_parser.add_argument('task_id', type=int, help='Task ID')
    
    # Runs command
    runs_parser = subparsers.add_parser('runs', help='Show recent runs')
    runs_parser.add_argument('--task', type=int, help='Filter by task ID')
    runs_parser.add_argument('--limit', type=int, default=20, help='Number of runs to show')
    
    # Alerts command
    alerts_parser = subparsers.add_parser('alerts', help='Show alerts')
    alerts_parser.add_argument('--all', action='store_true', help='Show all alerts')
    
    # Ack command
    ack_parser = subparsers.add_parser('ack', help='Acknowledge alert')
    ack_parser.add_argument('alert_id', type=int, help='Alert ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = TaskManagementCLI()
    
    if args.command == 'list':
        cli.list_tasks(args.active)
    elif args.command == 'show':
        cli.show_task(args.task_id)
    elif args.command == 'create':
        cli.create_task(args.name, args.script, args.description, 
                       args.max_retries, args.timeout)
    elif args.command == 'schedule':
        cli.add_schedule(args.task_id, args.type, args.config)
    elif args.command == 'depend':
        cli.add_dependency(args.task_id, args.depends_on, args.type)
    elif args.command == 'toggle':
        cli.toggle_task(args.task_id)
    elif args.command == 'runs':
        cli.show_runs(args.task, args.limit)
    elif args.command == 'alerts':
        cli.show_alerts(not args.all)
    elif args.command == 'ack':
        cli.acknowledge_alert(args.alert_id)

if __name__ == '__main__':
    main()