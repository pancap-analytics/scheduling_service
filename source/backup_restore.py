# SchedulerService/backup_restore.py
"""
Backup and restore utility for scheduler database.
Handles configuration and task data backup/restore.
"""

import os
import sys
import json
import argparse
import psycopg2
from datetime import datetime
import subprocess
import zipfile
import shutil

from production_config import DATABASE_CONFIG, PROJECT_ROOT

class SchedulerBackupRestore:
    def __init__(self):
        self.db_config = DATABASE_CONFIG
        self.backup_dir = os.path.join(PROJECT_ROOT, "SchedulerService", "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        
    def create_backup(self, include_history=True, backup_name=None):
        """Create a backup of the scheduler database."""
        if not backup_name:
            backup_name = f"scheduler_backup_{datetime.now():%Y%m%d_%H%M%S}"
        
        backup_path = os.path.join(self.backup_dir, backup_name)
        os.makedirs(backup_path, exist_ok=True)
        
        print(f"Creating backup: {backup_name}")
        
        try:
            # Connect to database
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            schema = self.db_config['schema']
            
            # Define tables to backup
            config_tables = [
                'scheduler_tasks',
                'task_schedules',
                'task_dependencies'
            ]
            
            history_tables = [
                'task_runs',
                'run_dependencies',
                'scheduler_alerts',
                'scheduler_health'
            ]
            
            tables_to_backup = config_tables
            if include_history:
                tables_to_backup.extend(history_tables)
            
            # Backup each table
            for table in tables_to_backup:
                print(f"  Backing up {table}...", end=" ")
                
                # Get table data
                cursor.execute(f"SELECT * FROM {schema}.{table}")
                rows = cursor.fetchall()
                
                # Get column names
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s 
                    ORDER BY ordinal_position
                """, (schema, table))
                columns = [row[0] for row in cursor.fetchall()]
                
                # Save to JSON
                table_data = {
                    'table': table,
                    'columns': columns,
                    'rows': rows,
                    'row_count': len(rows)
                }
                
                # Convert datetime objects to strings
                for row in table_data['rows']:
                    for i, value in enumerate(row):
                        if isinstance(value, datetime):
                            row[i] = value.isoformat()
                
                # Write to file
                table_file = os.path.join(backup_path, f"{table}.json")
                with open(table_file, 'w') as f:
                    json.dump(table_data, f, indent=2, default=str)
                
                print(f"✓ ({len(rows)} rows)")
            
            # Save metadata
            metadata = {
                'backup_name': backup_name,
                'timestamp': datetime.now().isoformat(),
                'database': self.db_config['database'],
                'schema': schema,
                'include_history': include_history,
                'tables': tables_to_backup
            }
            
            metadata_file = os.path.join(backup_path, 'metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Create ZIP archive
            zip_file = os.path.join(self.backup_dir, f"{backup_name}.zip")
            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(backup_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, backup_path)
                        zf.write(file_path, arcname)
            
            # Clean up temporary directory
            shutil.rmtree(backup_path)
            
            print(f"\nBackup completed: {zip_file}")
            print(f"Size: {os.path.getsize(zip_file) / 1024 / 1024:.2f} MB")
            
            cursor.close()
            conn.close()
            
            return zip_file
            
        except Exception as e:
            print(f"\n✗ Backup failed: {e}")
            return None
    
    def list_backups(self):
        """List available backups."""
        print("Available backups:")
        print("-" * 60)
        
        backups = []
        for file in os.listdir(self.backup_dir):
            if file.endswith('.zip'):
                file_path = os.path.join(self.backup_dir, file)
                size = os.path.getsize(file_path) / 1024 / 1024
                modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                backups.append((file, size, modified))
        
        if not backups:
            print("No backups found.")
            return
        
        # Sort by date
        backups.sort(key=lambda x: x[2], reverse=True)
        
        for backup, size, modified in backups:
            print(f"{backup:<40} {size:>8.2f} MB   {modified:%Y-%m-%d %H:%M}")
    
    def restore_backup(self, backup_file, tables_to_restore=None, dry_run=False):
        """Restore from a backup file."""
        if not backup_file.endswith('.zip'):
            backup_file += '.zip'
        
        backup_path = os.path.join(self.backup_dir, backup_file)
        if not os.path.exists(backup_path):
            print(f"Backup file not found: {backup_path}")
            return False
        
        print(f"Restoring from: {backup_file}")
        if dry_run:
            print("*** DRY RUN MODE - No changes will be made ***")
        
        temp_dir = os.path.join(self.backup_dir, 'temp_restore')
        
        try:
            # Extract backup
            print("Extracting backup...", end=" ")
            with zipfile.ZipFile(backup_path, 'r') as zf:
                zf.extractall(temp_dir)
            print("✓")
            
            # Read metadata
            with open(os.path.join(temp_dir, 'metadata.json'), 'r') as f:
                metadata = json.load(f)
            
            print(f"Backup created: {metadata['timestamp']}")
            print(f"Schema: {metadata['schema']}")
            
            if not dry_run:
                # Connect to database
                conn = psycopg2.connect(**self.db_config)
                cursor = conn.cursor()
                schema = self.db_config['schema']
            
            # Determine tables to restore
            if tables_to_restore:
                tables = [t for t in tables_to_restore if t in metadata['tables']]
            else:
                tables = metadata['tables']
            
            print(f"\nRestoring {len(tables)} tables:")
            
            for table in tables:
                table_file = os.path.join(temp_dir, f"{table}.json")
                if not os.path.exists(table_file):
                    print(f"  ✗ {table} - backup file not found")
                    continue
                
                with open(table_file, 'r') as f:
                    table_data = json.load(f)
                
                print(f"  {table} ({table_data['row_count']} rows)...", end=" ")
                
                if not dry_run:
                    # Clear existing data
                    cursor.execute(f"TRUNCATE TABLE {schema}.{table} CASCADE")
                    
                    # Restore data
                    if table_data['rows']:
                        # Build insert query
                        columns = table_data['columns']
                        placeholders = ','.join(['%s'] * len(columns))
                        insert_query = f"""
                            INSERT INTO {schema}.{table} ({','.join(columns)})
                            VALUES ({placeholders})
                        """
                        
                        # Convert string dates back to datetime
                        rows = []
                        for row in table_data['rows']:
                            new_row = []
                            for value in row:
                                if isinstance(value, str) and 'T' in value:
                                    try:
                                        new_row.append(datetime.fromisoformat(value))
                                    except:
                                        new_row.append(value)
                                else:
                                    new_row.append(value)
                            rows.append(tuple(new_row))
                        
                        # Insert data
                        cursor.executemany(insert_query, rows)
                
                print("✓")
            
            if not dry_run:
                # Reset sequences
                print("\nResetting sequences...", end=" ")
                cursor.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{schema}.scheduler_tasks', 'task_id'), 
                           COALESCE(MAX(task_id), 1)) FROM {schema}.scheduler_tasks;
                    SELECT setval(pg_get_serial_sequence('{schema}.task_runs', 'run_id'), 
                           COALESCE(MAX(run_id), 1)) FROM {schema}.task_runs;
                    SELECT setval(pg_get_serial_sequence('{schema}.scheduler_alerts', 'alert_id'), 
                           COALESCE(MAX(alert_id), 1)) FROM {schema}.scheduler_alerts;
                """)
                print("✓")
                
                conn.commit()
                cursor.close()
                conn.close()
                
                print("\nRestore completed successfully!")
            else:
                print("\nDry run completed. No changes made.")
            
            # Clean up
            shutil.rmtree(temp_dir)
            return True
            
        except Exception as e:
            print(f"\n✗ Restore failed: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False
    
    def export_config(self, output_file=None):
        """Export task configuration to a file."""
        if not output_file:
            output_file = f"scheduler_config_{datetime.now():%Y%m%d_%H%M%S}.json"
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            schema = self.db_config['schema']
            
            # Get all tasks with schedules and dependencies
            cursor.execute(f"""
                SELECT 
                    t.task_id, t.task_name, t.script_path, t.description,
                    t.is_active, t.max_retries, t.retry_delay_seconds, t.timeout_seconds,
                    json_agg(DISTINCT jsonb_build_object(
                        'schedule_type', s.schedule_type,
                        'schedule_config', s.schedule_config,
                        'is_active', s.is_active
                    )) FILTER (WHERE s.schedule_id IS NOT NULL) as schedules,
                    json_agg(DISTINCT jsonb_build_object(
                        'depends_on_task', dt.task_name,
                        'dependency_type', d.dependency_type
                    )) FILTER (WHERE d.dependency_id IS NOT NULL) as dependencies
                FROM {schema}.scheduler_tasks t
                LEFT JOIN {schema}.task_schedules s ON t.task_id = s.task_id
                LEFT JOIN {schema}.task_dependencies d ON t.task_id = d.task_id
                LEFT JOIN {schema}.scheduler_tasks dt ON d.depends_on_task_id = dt.task_id
                GROUP BY t.task_id
                ORDER BY t.task_name
            """)
            
            tasks = []
            for row in cursor.fetchall():
                task = {
                    'task_name': row[1],
                    'script_path': row[2],
                    'description': row[3],
                    'is_active': row[4],
                    'max_retries': row[5],
                    'retry_delay_seconds': row[6],
                    'timeout_seconds': row[7],
                    'schedules': row[8] if row[8] else [],
                    'dependencies': row[9] if row[9] else []
                }
                tasks.append(task)
            
            config = {
                'export_date': datetime.now().isoformat(),
                'task_count': len(tasks),
                'tasks': tasks
            }
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"Configuration exported to: {output_file}")
            print(f"Tasks exported: {len(tasks)}")
            
            cursor.close()
            conn.close()
            
            return output_file
            
        except Exception as e:
            print(f"Export failed: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description='Scheduler Backup/Restore Utility')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create backup')
    backup_parser.add_argument('--name', help='Backup name')
    backup_parser.add_argument('--no-history', action='store_true', 
                              help='Exclude run history from backup')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List backups')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore backup')
    restore_parser.add_argument('backup', help='Backup file name')
    restore_parser.add_argument('--tables', nargs='+', help='Specific tables to restore')
    restore_parser.add_argument('--dry-run', action='store_true', 
                               help='Show what would be restored without making changes')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration')
    export_parser.add_argument('--output', help='Output file name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    utility = SchedulerBackupRestore()
    
    if args.command == 'backup':
        utility.create_backup(
            include_history=not args.no_history,
            backup_name=args.name
        )
    elif args.command == 'list':
        utility.list_backups()
    elif args.command == 'restore':
        utility.restore_backup(
            args.backup,
            tables_to_restore=args.tables,
            dry_run=args.dry_run
        )
    elif args.command == 'export':
        utility.export_config(args.output)

if __name__ == '__main__':
    main()