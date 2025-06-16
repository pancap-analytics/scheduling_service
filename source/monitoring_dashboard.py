# # monitoring_dashboard.py - Enhanced version with dependencies and resource monitoring
# from flask import Flask, jsonify, request, render_template_string, send_from_directory
# import os
# import sys
# import json
# import psutil
# import logging
# from datetime import datetime, timedelta
# from flask_cors import CORS
# from threading import Thread
# import time
# import traceback
# import subprocess

# # Import database models
# try:
#     from db_models import DatabaseManager, TaskManager, RunManager, HealthManager, AlertManager
# except ImportError:
#     print("Warning: db_models not found, running in limited mode")

# app = Flask(__name__)
# CORS(app)

# # Set up template directory
# template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
# if not os.path.exists(template_dir):
#     os.makedirs(template_dir)

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# # Global references
# scheduler = None
# task_processes = {}  # Track running processes for resource monitoring
# task_dependencies = {}  # Store task dependencies

# def set_scheduler(scheduler_instance):
#     """Set the scheduler instance for the dashboard"""
#     global scheduler
#     scheduler = scheduler_instance
#     logger.info("Scheduler instance set in dashboard")

# # HTML Pages Routes
# @app.route('/')
# def dashboard():
#     """Main dashboard page"""
#     return send_from_directory(template_dir, 'dashboard.html')

# @app.route('/tasks')
# def tasks_page():
#     """Tasks management page"""
#     return send_from_directory(template_dir, 'tasks.html')

# @app.route('/logs')
# def logs_page():
#     """Logs viewer page"""
#     return send_from_directory(template_dir, 'logs.html')

# @app.route('/settings')
# def settings_page():
#     """Settings page"""
#     return send_from_directory(template_dir, 'settings.html')

# # API Routes
# @app.route('/api/status')
# def api_status():
#     """Get system status"""
#     try:
#         cpu_percent = psutil.cpu_percent(interval=1)
#         memory = psutil.virtual_memory()
#         disk = psutil.disk_usage('/')
        
#         # Get scheduler status
#         scheduler_status = "Unknown"
#         if scheduler:
#             scheduler_status = "Running" if hasattr(scheduler, 'scheduler') and scheduler.scheduler.running else "Stopped"
        
#         # Get running tasks count
#         running_tasks = len([p for p in task_processes.values() if p and p.poll() is None])
        
#         return jsonify({
#             'status': 'online',
#             'timestamp': datetime.now().isoformat(),
#             'system': {
#                 'cpu_percent': cpu_percent,
#                 'memory_percent': memory.percent,
#                 'memory_used_mb': memory.used / (1024 * 1024),
#                 'memory_total_mb': memory.total / (1024 * 1024),
#                 'disk_percent': disk.percent,
#                 'disk_used_gb': disk.used / (1024 * 1024 * 1024),
#                 'disk_total_gb': disk.total / (1024 * 1024 * 1024)
#             },
#             'scheduler': {
#                 'status': scheduler_status,
#                 'uptime': get_uptime(),
#                 'running_tasks': running_tasks
#             }
#         })
#     except Exception as e:
#         logger.error(f"Error getting status: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/tasks', methods=['GET'])
# def api_get_tasks():
#     """Get all tasks with enhanced information"""
#     try:
#         tasks = []
#         if scheduler and hasattr(scheduler, 'scheduler'):
#             jobs = scheduler.scheduler.get_jobs()
            
#             for job in jobs:
#                 # Get process info if task is running
#                 process_info = None
#                 if job.id in task_processes:
#                     proc = task_processes[job.id]
#                     if proc and proc.poll() is None:
#                         try:
#                             ps_proc = psutil.Process(proc.pid)
#                             process_info = {
#                                 'cpu_percent': ps_proc.cpu_percent(interval=0.1),
#                                 'memory_mb': ps_proc.memory_info().rss / (1024 * 1024),
#                                 'runtime': (datetime.now() - datetime.fromtimestamp(ps_proc.create_time())).total_seconds()
#                             }
#                         except:
#                             pass
                
#                 task_info = {
#                     'id': job.id,
#                     'name': job.name or job.id,
#                     'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
#                     'schedule': str(job.trigger),
#                     'active': job.next_run_time is not None,
#                     'script_path': job.kwargs.get('script_path', 'Unknown'),
#                     'last_run': None,  # Would need to track this
#                     'is_running': job.id in task_processes and task_processes[job.id] and task_processes[job.id].poll() is None,
#                     'process_info': process_info,
#                     'dependencies': task_dependencies.get(job.id, [])
#                 }
                
#                 # Add job details if available
#                 if hasattr(job, 'kwargs'):
#                     task_info.update({
#                         'python_path': job.kwargs.get('python_path'),
#                         'working_directory': job.kwargs.get('working_directory'),
#                         'arguments': job.kwargs.get('arguments'),
#                         'description': job.kwargs.get('description')
#                     })
                
#                 tasks.append(task_info)
        
#         return jsonify({
#             'status': 'success',
#             'tasks': tasks,
#             'count': len(tasks)
#         })
#     except Exception as e:
#         logger.error(f"Error getting tasks: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# # @app.route('/api/tasks/<task_name>/run', methods=['POST'])
# # def api_run_task(task_name):
# #     """Run a task immediately with resource tracking"""
# #     try:
# #         if scheduler and hasattr(scheduler, 'scheduler'):
# #             job = scheduler.scheduler.get_job(task_name)
# #             if job:
# #                 # Check dependencies first
# #                 deps = task_dependencies.get(task_name, [])
# #                 for dep in deps:
# #                     if dep in task_processes and task_processes[dep] and task_processes[dep].poll() is None:
# #                         return jsonify({
# #                             'status': 'error',
# #                             'message': f'Cannot run: dependency "{dep}" is still running'
# #                         }), 400
                
# #                 # Run the task
# #                 script_path = job.kwargs.get('script_path')
# #                 python_path = job.kwargs.get('python_path', sys.executable)
# #                 working_dir = job.kwargs.get('working_directory')
# #                 arguments = job.kwargs.get('arguments', '')
                
# #                 # Build command
# #                 cmd = [python_path, script_path]
# #                 if arguments:
# #                     cmd.extend(arguments.split())
                
# #                 # Start process
# #                 process = subprocess.Popen(
# #                     cmd,
# #                     cwd=working_dir,
# #                     stdout=subprocess.PIPE,
# #                     stderr=subprocess.PIPE,
# #                     universal_newlines=True
# #                 )
                
# #                 # Track the process
# #                 task_processes[task_name] = process
                
# #                 return jsonify({
# #                     'status': 'success',
# #                     'message': f'Task {task_name} started',
# #                     'pid': process.pid
# #                 })
# #             else:
# #                 return jsonify({
# #                     'status': 'error',
# #                     'message': f'Task {task_name} not found'
# #                 }), 404
# #         else:
# #             return jsonify({
# #                 'status': 'error',
# #                 'message': 'Scheduler not available'
# #             }), 503
# #     except Exception as e:
# #         logger.error(f"Error running task {task_name}: {str(e)}")
# #         return jsonify({'status': 'error', 'message': str(e)}), 500

# # In monitoring_dashboard.py

# @app.route('/api/tasks/<task_name>/run', methods=['POST'])
# def api_run_task(task_name):
#     """Run a task immediately by looking up its name."""
#     try:
#         if not (scheduler and hasattr(scheduler, 'scheduler')):
#             return jsonify({'status': 'error', 'message': 'Scheduler not available'}), 503

#         # Find the job by iterating through all jobs and matching the name
#         job_to_run = None
#         for job in scheduler.scheduler.get_jobs():
#             if job.name == task_name:
#                 job_to_run = job
#                 break

#         if job_to_run:
#             logger.info(f"Found job '{job_to_run.name}' with ID '{job_to_run.id}'. Triggering manual run.")
            
#             # Use the existing logic to run the task, but with the correctly found job object
#             deps = task_dependencies.get(job_to_run.name, [])
#             for dep in deps:
#                 if dep in task_processes and task_processes[dep] and task_processes[dep].poll() is None:
#                     return jsonify({
#                         'status': 'error',
#                         'message': f'Cannot run: dependency "{dep}" is still running'
#                     }), 400

#             script_path = job_to_run.kwargs.get('script_path')
#             python_path = job_to_run.kwargs.get('python_path', sys.executable)
#             working_dir = job_to_run.kwargs.get('working_directory')
#             arguments = job_to_run.kwargs.get('arguments', '')
            
#             cmd = [python_path, script_path]
#             if arguments:
#                 cmd.extend(arguments.split())
            
#             process = subprocess.Popen(
#                 cmd,
#                 cwd=working_dir,
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 universal_newlines=True
#             )
            
#             task_processes[job_to_run.id] = process # Track by unique ID

#             return jsonify({
#                 'status': 'success',
#                 'message': f'Task {task_name} started',
#                 'pid': process.pid
#             })
#         else:
#             logger.warning(f"Manual run requested for task '{task_name}', but it was not found.")
#             return jsonify({
#                 'status': 'error',
#                 'message': f'Task {task_name} not found'
#             }), 404
            
#     except Exception as e:
#         logger.error(f"Error running task {task_name}: {str(e)}", exc_info=True)
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/tasks', methods=['POST'])
# def api_create_task():
#     """Create a new task with dependency support"""
#     try:
#         data = request.json
        
#         # Validate required fields
#         required_fields = ['name', 'script_path', 'schedule']
#         for field in required_fields:
#             if field not in data:
#                 return jsonify({
#                     'status': 'error',
#                     'message': f'Missing required field: {field}'
#                 }), 400
        
#         # Store dependencies if provided
#         if 'dependencies' in data:
#             task_dependencies[data['name']] = data['dependencies']
        
#         # Add task to scheduler
#         if scheduler and hasattr(scheduler, 'add_task'):
#             scheduler.add_task(data)
#             return jsonify({
#                 'status': 'success',
#                 'message': f'Task {data["name"]} created successfully'
#             })
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Scheduler not available'
#             }), 503
            
#     except Exception as e:
#         logger.error(f"Error creating task: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/tasks/<task_name>', methods=['PUT'])
# def api_update_task(task_name):
#     """Update an existing task"""
#     try:
#         data = request.json
        
#         # Update dependencies if provided
#         if 'dependencies' in data:
#             task_dependencies[task_name] = data['dependencies']
        
#         if scheduler and hasattr(scheduler, 'update_task'):
#             scheduler.update_task(task_name, data)
#             return jsonify({
#                 'status': 'success',
#                 'message': f'Task {task_name} updated successfully'
#             })
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Scheduler not available'
#             }), 503
            
#     except Exception as e:
#         logger.error(f"Error updating task {task_name}: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/tasks/<task_name>', methods=['DELETE'])
# def api_delete_task(task_name):
#     """Delete a task"""
#     try:
#         # Remove dependencies
#         if task_name in task_dependencies:
#             del task_dependencies[task_name]
        
#         # Remove from process tracking
#         if task_name in task_processes:
#             proc = task_processes[task_name]
#             if proc and proc.poll() is None:
#                 proc.terminate()
#             del task_processes[task_name]
        
#         if scheduler and hasattr(scheduler, 'remove_task'):
#             scheduler.remove_task(task_name)
#             return jsonify({
#                 'status': 'success',
#                 'message': f'Task {task_name} deleted successfully'
#             })
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Scheduler not available'
#             }), 503
            
#     except Exception as e:
#         logger.error(f"Error deleting task {task_name}: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/tasks/<task_name>/resources')
# def api_get_task_resources(task_name):
#     """Get real-time resource usage for a running task"""
#     try:
#         if task_name in task_processes:
#             proc = task_processes[task_name]
#             if proc and proc.poll() is None:
#                 try:
#                     ps_proc = psutil.Process(proc.pid)
                    
#                     # Get detailed resource info
#                     cpu_times = ps_proc.cpu_times()
#                     memory_info = ps_proc.memory_info()
#                     io_counters = ps_proc.io_counters() if hasattr(ps_proc, 'io_counters') else None
                    
#                     return jsonify({
#                         'status': 'success',
#                         'task_name': task_name,
#                         'pid': proc.pid,
#                         'resources': {
#                             'cpu_percent': ps_proc.cpu_percent(interval=0.1),
#                             'cpu_times': {
#                                 'user': cpu_times.user,
#                                 'system': cpu_times.system
#                             },
#                             'memory': {
#                                 'rss_mb': memory_info.rss / (1024 * 1024),
#                                 'vms_mb': memory_info.vms / (1024 * 1024),
#                                 'percent': ps_proc.memory_percent()
#                             },
#                             'io': {
#                                 'read_mb': io_counters.read_bytes / (1024 * 1024) if io_counters else 0,
#                                 'write_mb': io_counters.write_bytes / (1024 * 1024) if io_counters else 0
#                             } if io_counters else None,
#                             'threads': ps_proc.num_threads(),
#                             'status': ps_proc.status(),
#                             'create_time': datetime.fromtimestamp(ps_proc.create_time()).isoformat(),
#                             'runtime_seconds': (datetime.now() - datetime.fromtimestamp(ps_proc.create_time())).total_seconds()
#                         }
#                     })
#                 except psutil.NoSuchProcess:
#                     return jsonify({
#                         'status': 'error',
#                         'message': 'Process no longer exists'
#                     }), 404
#             else:
#                 return jsonify({
#                     'status': 'error',
#                     'message': 'Task is not running'
#                 }), 404
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Task not found or not running'
#             }), 404
            
#     except Exception as e:
#         logger.error(f"Error getting resources for task {task_name}: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/logs/<task_name>')
# def api_get_task_logs(task_name):
#     """Get logs for a specific task"""
#     try:
#         log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'tasks')
#         log_file = os.path.join(log_dir, f'{task_name}.log')
        
#         if os.path.exists(log_file):
#             with open(log_file, 'r') as f:
#                 logs = f.readlines()
                
#             # Parse logs into structured format
#             parsed_logs = []
#             for line in logs[-100:]:  # Last 100 lines
#                 if line.strip():
#                     parsed_logs.append({
#                         'timestamp': line[:23] if len(line) > 23 else '',
#                         'message': line[23:].strip() if len(line) > 23 else line.strip()
#                     })
            
#             return jsonify({
#                 'status': 'success',
#                 'task_name': task_name,
#                 'logs': parsed_logs
#             })
#         else:
#             return jsonify({
#                 'status': 'success',
#                 'task_name': task_name,
#                 'logs': [],
#                 'message': 'No logs found for this task'
#             })
            
#     except Exception as e:
#         logger.error(f"Error getting logs for task {task_name}: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/logs/system')
# def api_get_system_logs():
#     """Get system logs"""
#     try:
#         log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
#         log_types = ['service.log', 'scheduler.log', 'dashboard.log', 'error.log']
        
#         all_logs = {}
#         for log_type in log_types:
#             log_file = os.path.join(log_dir, log_type)
#             if os.path.exists(log_file):
#                 with open(log_file, 'r') as f:
#                     lines = f.readlines()
#                     all_logs[log_type] = lines[-50:]  # Last 50 lines per log type
        
#         return jsonify({
#             'status': 'success',
#             'logs': all_logs
#         })
        
#     except Exception as e:
#         logger.error(f"Error getting system logs: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/task/<task_name>/history')
# def api_get_task_history(task_name):
#     """Get execution history for a task"""
#     try:
#         # This would typically query a database
#         # For now, return mock data with resource usage
#         history = [
#             {
#                 'run_id': 1,
#                 'start_time': (datetime.now() - timedelta(hours=1)).isoformat(),
#                 'end_time': (datetime.now() - timedelta(hours=1, minutes=-5)).isoformat(),
#                 'status': 'success',
#                 'duration': 300,
#                 'output': 'Task completed successfully',
#                 'resources': {
#                     'peak_cpu': 45.2,
#                     'peak_memory_mb': 256.5,
#                     'total_io_mb': 1024
#                 }
#             }
#         ]
        
#         return jsonify({
#             'status': 'success',
#             'task_name': task_name,
#             'history': history
#         })
        
#     except Exception as e:
#         logger.error(f"Error getting history for task {task_name}: {str(e)}")
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/api/dependencies')
# def api_get_dependencies():
#     """Get all task dependencies"""
#     return jsonify({
#         'status': 'success',
#         'dependencies': task_dependencies
#     })

# def get_uptime():
#     """Get scheduler uptime"""
#     # This would track actual uptime
#     return "Running for 0 days, 0:00:00"

# # Background thread to clean up finished processes
# def cleanup_processes():
#     """Clean up finished processes from tracking"""
#     while True:
#         try:
#             for task_name, proc in list(task_processes.items()):
#                 if proc and proc.poll() is not None:
#                     # Process has finished
#                     del task_processes[task_name]
#         except:
#             pass
#         time.sleep(5)

# # Start cleanup thread
# cleanup_thread = Thread(target=cleanup_processes, daemon=True)
# cleanup_thread.start()

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5001, debug=True)

# monitoring_dashboard.py - Final version using Flask's application context
import os
import sys
import json
import psutil
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, current_app
from flask_cors import CORS
import subprocess
import re

# --- Initialization ---
app = Flask(__name__)
CORS(app)

# Define the template directory relative to this file's location
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
logger = logging.getLogger(__name__)

# This dictionary is a simple way to track running processes.
# In a real production system, this state should be managed in the database for resilience.
task_processes = {}
# This tracks dependencies. This should also ideally be in the database.
task_dependencies = {}


# --- HTML Pages Routes ---
# These routes serve the static HTML pages for the UI.

@app.route('/')
def dashboard_page():
    return send_from_directory(template_dir, 'dashboard.html')

@app.route('/tasks')
def tasks_page():
    return send_from_directory(template_dir, 'tasks.html')

@app.route('/logs')
def logs_page():
    return send_from_directory(template_dir, 'logs.html')

@app.route('/settings')
def settings_page():
    return send_from_directory(template_dir, 'settings.html')


# --- API Routes ---

def get_uptime():
    """Placeholder for getting scheduler uptime."""
    # A real implementation would track the start time of the service.
    return "Running for 0 days, 0:00:00"

@app.route('/api/status')
def api_status():
    """Get overall system and scheduler status."""
    scheduler = current_app.config.get('SCHEDULER')
    
    scheduler_status = "Not Initialized"
    if scheduler and hasattr(scheduler, 'scheduler'):
        scheduler_status = "Running" if scheduler.scheduler.running else "Stopped"

    # Get running tasks count from our tracked processes
    running_tasks_count = len([p for p in task_processes.values() if p and p.poll() is None])

    return jsonify({
        'status': 'online',
        'scheduler': {
            'status': scheduler_status,
            'uptime': get_uptime(),
            'running_tasks': running_tasks_count
        }
    })

@app.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """Get a list of all scheduled tasks, preserving all original fields."""
    scheduler = current_app.config.get('SCHEDULER')
    if not (scheduler and hasattr(scheduler, 'scheduler')):
        return jsonify({'status': 'error', 'message': 'Scheduler service not available'}), 503

    tasks = []
    try:
        for job in scheduler.scheduler.get_jobs():
            process_info = None
            is_running = job.id in task_processes and task_processes[job.id].poll() is None
            if is_running:
                try:
                    p = psutil.Process(task_processes[job.id].pid)
                    process_info = {
                        'cpu_percent': p.cpu_percent(interval=0.1),
                        'memory_mb': p.memory_info().rss / (1024 * 1024),
                        'runtime': (datetime.now() - datetime.fromtimestamp(p.create_time())).total_seconds()
                    }
                except psutil.NoSuchProcess:
                    is_running = False # Process ended but wasn't cleaned up yet
                except Exception as e:
                    logger.warning(f"Could not get process info for {job.id}: {e}")

            task_info = {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'schedule': str(job.trigger),
                'active': job.next_run_time is not None,
                'is_running': is_running,
                'process_info': process_info,
                'dependencies': task_dependencies.get(job.id, []),
                'script_path': job.kwargs.get('script_path', 'N/A'),
                'python_path': job.kwargs.get('python_path'),
                'working_directory': job.kwargs.get('working_directory'),
                'arguments': job.kwargs.get('arguments'),
                'description': job.kwargs.get('description'),
                'last_run': None, # This would require DB persistence to track properly
            }
            tasks.append(task_info)
        return jsonify({'status': 'success', 'tasks': tasks, 'count': len(tasks)})
    except Exception as e:
        logger.error(f"Error getting tasks: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


def parse_schedule_from_frontend(data):
    """
    Parses the 'schedule' string from the frontend into the
    'schedule_type' and 'schedule_config' dict needed by the backend.
    """
    schedule_str = data.get('schedule', '')
    
    # Case 1: One-time job (ISO format date string)
    try:
        datetime.fromisoformat(schedule_str.replace('Z', '+00:00'))
        return 'date', {'run_date': schedule_str}
    except (ValueError, TypeError):
        pass

    # Case 2: Cron expression
    # This is a simple regex; a more robust one could be used if needed.
    if re.match(r'^([\d\*\/\-,]+ ){4}[\d\*\/\-,]+$', schedule_str):
        cron_parts = schedule_str.split()
        return 'cron', {
            'minute': cron_parts[0],
            'hour': cron_parts[1],
            'day': cron_parts[2],
            'month': cron_parts[3],
            'day_of_week': cron_parts[4]
        }
        
    raise ValueError(f"Invalid or unsupported schedule format: {schedule_str}")


@app.route('/api/tasks', methods=['POST'])
def api_create_task():
    """Creates a new task and reloads the scheduler."""
    scheduler = current_app.config.get('SCHEDULER')
    if not (scheduler and hasattr(scheduler, 'task_manager')):
        return jsonify({'status': 'error', 'message': 'Scheduler service not available'}), 503

    data = request.json
    try:
        # Step 1: Parse the schedule sent from the frontend
        schedule_type, schedule_config = parse_schedule_from_frontend(data)

        # Step 2: Create the task in the database
        task_id = scheduler.task_manager.create_task(
            task_name=data['name'],
            script_path=data['script_path'],
            description=data.get('description'),
        )
        # Step 3: Add the parsed schedule
        scheduler.task_manager.add_schedule(task_id, schedule_type, schedule_config)

        # Step 4: Tell the running scheduler to load the new task
        scheduler.load_tasks_from_db()

        return jsonify({'status': 'success', 'message': 'Task created and scheduler reloaded.'})
    except Exception as e:
        logger.error(f"Error creating task: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/tasks/<task_id>', methods=['PUT'])
def api_update_task(task_id):
    """Updates an existing task."""
    scheduler = current_app.config.get('SCHEDULER')
    if not (scheduler and hasattr(scheduler, 'task_manager')):
        return jsonify({'status': 'error', 'message': 'Scheduler service not available'}), 503

    data = request.json
    try:
        # Update task properties (name, script_path, etc.)
        scheduler.task_manager.update_task(task_id, **data)
        
        # If schedule is being updated, handle that as well
        if 'schedule' in data:
            schedule_type, schedule_config = parse_schedule_from_frontend(data)
            # This would require a method like `update_schedule` in TaskManager
            # For now, we'll assume it replaces the old one.
            scheduler.task_manager.add_schedule(task_id, schedule_type, schedule_config, replace=True)

        # Reload all tasks in the scheduler to apply changes
        scheduler.load_tasks_from_db()
        return jsonify({'status': 'success', 'message': f'Task {task_id} updated.'})
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/tasks/<task_name>/run', methods=['POST'])
def api_run_task(task_name):
    """Run a task immediately by name."""
    scheduler = current_app.config.get('SCHEDULER')
    if not (scheduler and hasattr(scheduler, 'scheduler')):
        return jsonify({'status': 'error', 'message': 'Scheduler not available'}), 503

    job_to_run = None
    for job in scheduler.scheduler.get_jobs():
        if job.name == task_name:
            job_to_run = job
            break

    if job_to_run:
        logger.info(f"Manual run triggered for job: {job_to_run.name} (ID: {job_to_run.id})")
        try:
            # Manually trigger the core execution logic
            scheduler.executor.submit(scheduler.execute_task, job_to_run.kwargs['task_id'])
            return jsonify({'status': 'success', 'message': f'Task {task_name} has been triggered to run.'})
        except Exception as e:
            logger.error(f"Error triggering job {job_to_run.id}: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': f"Failed to run job: {e}"}), 500
    else:
        logger.warning(f"Manual run requested for task '{task_name}', but it was not found.")
        return jsonify({'status': 'error', 'message': f'Task "{task_name}" not found'}), 404

# Main entry point for direct execution (for testing)
if __name__ == '__main__':
    # This part is for standalone testing only
    # In production, local_scheduler_service.py will run this
    app.run(host='0.0.0.0', port=5001, debug=True)

