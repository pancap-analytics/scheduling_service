# SchedulerService/db_models.py
import os
import json
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from production_config import DATABASE_CONFIG as DB_CONFIG, DATABASE_SCHEMA as SCHEMA_NAME

logger = logging.getLogger(__name__)

# # Database configuration
# DB_CONFIG = {
#     'host': '10.0.10.126',
#     'port': 5432,
#     'database': 'coder',
#     'user': 'postgres',
#     'password': 'Postgres'
# }
# SCHEMA_NAME = 'nicks_workspace'

class DatabaseManager:
    """Manages database connections and operations for the scheduler."""
    
    def __init__(self, min_conn=1, max_conn=10):
        self.pool = SimpleConnectionPool(
            min_conn, max_conn,
            **DB_CONFIG
        )
        self.schema = SCHEMA_NAME
    
    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Context manager for database connections."""
        conn = self.pool.getconn()
        try:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a SELECT query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT query and return the new ID."""
        with self.get_cursor() as cursor:
            # Check if query has RETURNING clause
            if "RETURNING" in query.upper():
                try:
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    # Get the first numeric column from result
                    for key, value in result.items():
                        if key.endswith('_id') and isinstance(value, int):
                            return value
                    # If no ID column found, return first value
                    return list(result.values())[0]
                except Exception as e:
                    # If RETURNING fails, fall back to non-RETURNING method
                    if "RETURNING" in str(e).upper():
                        # Remove RETURNING clause
                        query_without_returning = query[:query.upper().rfind("RETURNING")]
                        cursor.execute(query_without_returning, params)
                        # Get the last inserted ID using currval
                        if "scheduler_tasks" in query:
                            cursor.execute(f"SELECT currval(pg_get_serial_sequence('{self.schema}.scheduler_tasks', 'task_id'))")
                        elif "task_schedules" in query:
                            cursor.execute(f"SELECT currval(pg_get_serial_sequence('{self.schema}.task_schedules', 'schedule_id'))")
                        elif "task_runs" in query:
                            cursor.execute(f"SELECT currval(pg_get_serial_sequence('{self.schema}.task_runs', 'run_id'))")
                        elif "scheduler_alerts" in query:
                            cursor.execute(f"SELECT currval(pg_get_serial_sequence('{self.schema}.scheduler_alerts', 'alert_id'))")
                        else:
                            raise Exception("Cannot determine sequence for table")
                        return cursor.fetchone()[0]
                    else:
                        raise
            else:
                # No RETURNING clause, execute normally
                cursor.execute(query, params)
                return cursor.lastrowid if hasattr(cursor, 'lastrowid') else 0

class TaskManager:
    """Manages task operations in the database."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.schema = SCHEMA_NAME
    
    def create_task(self, task_name: str, script_path: str, description: str = None,
                   max_retries: int = 3, timeout_seconds: int = 3600) -> int:
        """Create a new task."""
        query = f"""
            INSERT INTO {self.schema}.scheduler_tasks 
            (task_name, script_path, description, max_retries, timeout_seconds)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING task_id
        """
        return self.db.execute_insert(query, (task_name, script_path, description, max_retries, timeout_seconds))
    
    def get_task(self, task_id: int = None, task_name: str = None) -> Optional[Dict]:
        """Get task by ID or name."""
        if task_id:
            query = f"SELECT * FROM {self.schema}.scheduler_tasks WHERE task_id = %s"
            params = (task_id,)
        else:
            query = f"SELECT * FROM {self.schema}.scheduler_tasks WHERE task_name = %s"
            params = (task_name,)
        
        results = self.db.execute_query(query, params)
        return results[0] if results else None
    
    def get_active_tasks(self) -> List[Dict]:
        """Get all active tasks."""
        query = f"""
            SELECT t.*, s.schedule_type, s.schedule_config, s.next_run_time
            FROM {self.schema}.scheduler_tasks t
            LEFT JOIN {self.schema}.task_schedules s ON t.task_id = s.task_id
            WHERE t.is_active = true AND (s.is_active = true OR s.is_active IS NULL)
        """
        return self.db.execute_query(query)
    
    def update_task(self, task_id: int, **kwargs) -> bool:
        """Update task properties."""
        allowed_fields = ['task_name', 'script_path', 'description', 'is_active', 
                         'max_retries', 'retry_delay_seconds', 'timeout_seconds']
        
        updates = []
        values = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = %s")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE {self.schema}.scheduler_tasks SET {', '.join(updates)} WHERE task_id = %s"
        return self.db.execute_update(query, tuple(values)) > 0
    
    def add_schedule(self, task_id: int, schedule_type: str, schedule_config: Dict) -> int:
        """Add a schedule to a task."""
        query = f"""
            INSERT INTO {self.schema}.task_schedules 
            (task_id, schedule_type, schedule_config)
            VALUES (%s, %s, %s)
            RETURNING schedule_id
        """
        return self.db.execute_insert(query, (task_id, schedule_type, json.dumps(schedule_config)))
    
    def add_dependency(self, task_id: int, depends_on_task_id: int, 
                      dependency_type: str = 'success') -> bool:
        """Add a dependency between tasks."""
        query = f"""
            INSERT INTO {self.schema}.task_dependencies 
            (task_id, depends_on_task_id, dependency_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (task_id, depends_on_task_id) DO UPDATE
            SET dependency_type = EXCLUDED.dependency_type
        """
        return self.db.execute_update(query, (task_id, depends_on_task_id, dependency_type)) > 0
    
    def get_dependencies(self, task_id: int) -> List[Dict]:
        """Get all dependencies for a task."""
        query = f"""
            SELECT d.*, t.task_name as depends_on_task_name
            FROM {self.schema}.task_dependencies d
            JOIN {self.schema}.scheduler_tasks t ON d.depends_on_task_id = t.task_id
            WHERE d.task_id = %s
        """
        return self.db.execute_query(query, (task_id,))

class RunManager:
    """Manages task run operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.schema = SCHEMA_NAME
    
    def create_run(self, task_id: int, triggered_by: str = 'schedule',
                  machine_name: str = None, process_id: int = None) -> int:
        """Create a new task run."""
        machine_name = machine_name or os.environ.get('COMPUTERNAME', 'unknown')
        query = f"""
            INSERT INTO {self.schema}.task_runs 
            (task_id, status, started_at, triggered_by, machine_name, process_id)
            VALUES (%s, 'pending', CURRENT_TIMESTAMP, %s, %s, %s)
            RETURNING run_id
        """
        return self.db.execute_insert(query, (task_id, triggered_by, machine_name, process_id))
    
    def update_run_status(self, run_id: int, status: str, exit_code: int = None,
                         error_message: str = None, log_file_path: str = None):
        """Update run status."""
        query = f"""
            UPDATE {self.schema}.task_runs 
            SET status = %s, 
                completed_at = CASE WHEN %s IN ('success', 'failed', 'timeout') THEN CURRENT_TIMESTAMP ELSE completed_at END,
                duration_seconds = CASE WHEN %s IN ('success', 'failed', 'timeout') 
                    THEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) ELSE duration_seconds END,
                exit_code = %s,
                error_message = %s,
                log_file_path = COALESCE(%s, log_file_path)
            WHERE run_id = %s
        """
        params = (status, status, status, exit_code, error_message, log_file_path, run_id)
        return self.db.execute_update(query, params) > 0
    
    def get_recent_runs(self, task_id: int = None, limit: int = 100) -> List[Dict]:
        """Get recent task runs."""
        if task_id:
            query = f"""
                SELECT r.*, t.task_name 
                FROM {self.schema}.task_runs r
                JOIN {self.schema}.scheduler_tasks t ON r.task_id = t.task_id
                WHERE r.task_id = %s
                ORDER BY r.started_at DESC
                LIMIT %s
            """
            params = (task_id, limit)
        else:
            query = f"""
                SELECT r.*, t.task_name 
                FROM {self.schema}.task_runs r
                JOIN {self.schema}.scheduler_tasks t ON r.task_id = t.task_id
                ORDER BY r.started_at DESC
                LIMIT %s
            """
            params = (limit,)
        
        return self.db.execute_query(query, params)
    
    def get_running_tasks(self) -> List[Dict]:
        """Get currently running tasks."""
        query = f"""
            SELECT r.*, t.task_name, t.timeout_seconds
            FROM {self.schema}.task_runs r
            JOIN {self.schema}.scheduler_tasks t ON r.task_id = t.task_id
            WHERE r.status = 'running'
            ORDER BY r.started_at
        """
        return self.db.execute_query(query)
    
    def check_dependencies_satisfied(self, task_id: int) -> bool:
        """Check if all dependencies for a task are satisfied."""
        query = f"""
            SELECT COUNT(*) as unsatisfied_count
            FROM {self.schema}.task_dependencies d
            WHERE d.task_id = %s
            AND NOT EXISTS (
                SELECT 1 FROM {self.schema}.task_runs r
                WHERE r.task_id = d.depends_on_task_id
                AND r.started_at >= CURRENT_DATE
                AND (
                    (d.dependency_type = 'success' AND r.status = 'success')
                    OR (d.dependency_type = 'completion' AND r.status IN ('success', 'failed'))
                    OR (d.dependency_type = 'failure' AND r.status = 'failed')
                )
            )
        """
        result = self.db.execute_query(query, (task_id,))
        return result[0]['unsatisfied_count'] == 0
    
    def create_run_dependency(self, run_id: int, depends_on_run_id: int):
        """Track dependency between runs."""
        query = f"""
            INSERT INTO {self.schema}.run_dependencies 
            (run_id, depends_on_run_id)
            VALUES (%s, %s)
        """
        return self.db.execute_update(query, (run_id, depends_on_run_id)) > 0

class HealthManager:
    """Manages service health monitoring."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.schema = SCHEMA_NAME
        self.service_name = "PythonSchedulerService"
        self.machine_name = os.environ.get('COMPUTERNAME', 'unknown')
    
    def update_heartbeat(self, status: str = 'healthy', metrics: Dict = None):
        """Update service heartbeat."""
        # First try to update existing record
        query_update = f"""
            UPDATE {self.schema}.scheduler_health 
            SET status = %s,
                last_heartbeat = CURRENT_TIMESTAMP,
                metrics = %s
            WHERE service_name = %s AND machine_name = %s
        """
        metrics_json = json.dumps(metrics) if metrics else None
        
        rows_updated = self.db.execute_update(query_update, 
            (status, metrics_json, self.service_name, self.machine_name))
        
        # If no rows updated, insert new record
        if rows_updated == 0:
            query_insert = f"""
                INSERT INTO {self.schema}.scheduler_health 
                (service_name, machine_name, status, metrics)
                VALUES (%s, %s, %s, %s)
            """
            self.db.execute_update(query_insert, 
                (self.service_name, self.machine_name, status, metrics_json))
        
        return True
    
    def get_service_health(self) -> List[Dict]:
        """Get health status of all services."""
        query = f"""
            SELECT * FROM {self.schema}.scheduler_health
            WHERE last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '5 minutes'
            ORDER BY last_heartbeat DESC
        """
        return self.db.execute_query(query)

class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.schema = SCHEMA_NAME
    
    def create_alert(self, alert_type: str, severity: str, message: str,
                    task_id: int = None, run_id: int = None, details: Dict = None):
        """Create a new alert."""
        query = f"""
            INSERT INTO {self.schema}.scheduler_alerts 
            (alert_type, severity, message, task_id, run_id, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING alert_id
        """
        details_json = json.dumps(details) if details else None
        return self.db.execute_insert(query, 
            (alert_type, severity, message, task_id, run_id, details_json))
    
    def get_unacknowledged_alerts(self, severity: str = None) -> List[Dict]:
        """Get unacknowledged alerts."""
        if severity:
            query = f"""
                SELECT * FROM {self.schema}.scheduler_alerts
                WHERE acknowledged = false AND severity = %s
                ORDER BY created_at DESC
            """
            params = (severity,)
        else:
            query = f"""
                SELECT * FROM {self.schema}.scheduler_alerts
                WHERE acknowledged = false
                ORDER BY created_at DESC
            """
            params = None
        
        return self.db.execute_query(query, params)
    
    def acknowledge_alert(self, alert_id: int, acknowledged_by: str = 'system'):
        """Acknowledge an alert."""
        query = f"""
            UPDATE {self.schema}.scheduler_alerts
            SET acknowledged = true,
                acknowledged_by = %s,
                acknowledged_at = CURRENT_TIMESTAMP
            WHERE alert_id = %s
        """
        return self.db.execute_update(query, (acknowledged_by, alert_id)) > 0