# # local_scheduler_service.py
# """
# Integrated scheduler service that manages both the task scheduler and web dashboard.
# """

# import sys
# import os
# import logging
# import threading
# import time
# from pathlib import Path

# # Setup local paths
# LOCAL_ROOT = Path(r"C:\SchedulerService")
# sys.path.insert(0, str(LOCAL_ROOT / "source"))

# # Import local config
# import production_config_local as production_config
# sys.modules['production_config'] = production_config

# # Setup logging
# from logging.handlers import RotatingFileHandler

# def setup_logging():
#     """Setup logging for the service."""
#     log_dir = LOCAL_ROOT / "logs"
#     log_dir.mkdir(exist_ok=True)
    
#     # Main log file
#     main_log = log_dir / "service.log"
    
#     # Configure root logger
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         handlers=[
#             RotatingFileHandler(main_log, maxBytes=10*1024*1024, backupCount=5),
#             logging.StreamHandler(sys.stdout)
#         ]
#     )
    
#     return logging.getLogger('LocalSchedulerService')

# logger = setup_logging()

# class IntegratedSchedulerService:
#     """Service that runs both scheduler and dashboard."""
    
#     def __init__(self):
#         self.scheduler = None
#         self.dashboard_thread = None
#         self.running = False
#         logger.info("Integrated Scheduler Service initialized")
    
#     def start_dashboard(self):
#         """Start the Flask dashboard in a separate thread."""
#         def run_dashboard():
#             try:
#                 logger.info("Starting dashboard server...")
                
#                 # Import Flask app
#                 from monitoring_dashboard import app
                
#                 # Start Flask app
#                 app.run(
#                     host=production_config.DASHBOARD_CONFIG['host'],
#                     port=production_config.DASHBOARD_CONFIG['port'],
#                     debug=production_config.DASHBOARD_CONFIG['debug'],
#                     use_reloader=False,
#                     threaded=True
#                 )
                
#             except Exception as e:
#                 logger.error(f"Dashboard error: {e}")
#                 import traceback
#                 logger.error(traceback.format_exc())
        
#         self.dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
#         self.dashboard_thread.start()
#         logger.info("Dashboard thread started")
    
#     def start_scheduler(self):
#         """Start the task scheduler."""
#         try:
#             logger.info("Starting task scheduler...")
            
#             # Import scheduler
#             from production_scheduler_core import ProductionScheduler
            
#             # Initialize scheduler
#             self.scheduler = ProductionScheduler()
            
#             # Start scheduler (this will block)
#             self.scheduler.start()
            
#         except Exception as e:
#             logger.error(f"Scheduler error: {e}")
#             import traceback
#             logger.error(traceback.format_exc())
    
#     def start(self):
#         """Start both dashboard and scheduler."""
#         logger.info("Starting Integrated Scheduler Service...")
        
#         try:
#             # Start dashboard first
#             self.start_dashboard()
            
#             # Give dashboard time to start
#             time.sleep(3)
            
#             # Start scheduler (this will block until stopped)
#             self.running = True
#             self.start_scheduler()
            
#         except KeyboardInterrupt:
#             logger.info("Service interrupted by user")
#         except Exception as e:
#             logger.error(f"Service error: {e}")
#             import traceback
#             logger.error(traceback.format_exc())
#         finally:
#             self.stop()
    
#     def stop(self):
#         """Stop the service."""
#         logger.info("Stopping Integrated Scheduler Service...")
        
#         self.running = False
        
#         if self.scheduler:
#             try:
#                 self.scheduler.shutdown()
#                 logger.info("Scheduler stopped")
#             except:
#                 pass
        
#         logger.info("Service stopped")

# # Service entry point
# if __name__ == '__main__':
#     service = IntegratedSchedulerService()
#     service.start()


# local_scheduler_service.py - Final version using app.config
import sys
import logging
import threading
from pathlib import Path

# Setup local paths
LOCAL_ROOT = Path(r"C:\SchedulerService")
sys.path.insert(0, str(LOCAL_ROOT / "source"))

# Import local config and components
import production_config_local as production_config
sys.modules['production_config'] = production_config

from production_scheduler_core import ProductionScheduler
from monitoring_dashboard import app # Only import the app object

from logging.handlers import RotatingFileHandler

def setup_logging():
    log_dir = LOCAL_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    main_log = log_dir / "service.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(main_log, maxBytes=10*1024*1024, backupCount=5),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('LocalSchedulerService')

logger = setup_logging()

class IntegratedSchedulerService:
    def __init__(self):
        self.scheduler_instance = None
        self.dashboard_thread = None
        self.is_running = False
        logger.info("Integrated Scheduler Service initialized")

    def start(self):
        """Start both dashboard and scheduler in the correct order."""
        logger.info("Starting Integrated Scheduler Service...")
        try:
            # 1. Initialize the scheduler
            logger.info("Initializing task scheduler instance...")
            self.scheduler_instance = ProductionScheduler()

            # 2. Store the scheduler instance in the Flask app's config
            logger.info("Injecting scheduler into dashboard application context...")
            app.config['SCHEDULER'] = self.scheduler_instance

            # 3. Start the dashboard in a background thread
            def run_dashboard():
                try:
                    logger.info("Starting dashboard server...")
                    app.run(
                        host=production_config.DASHBOARD_CONFIG['host'],
                        port=production_config.DASHBOARD_CONFIG['port'],
                        debug=False, # Debug should be off for a service
                        use_reloader=False
                    )
                except Exception as e:
                    logger.error(f"Dashboard thread error: {e}", exc_info=True)

            self.dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
            self.dashboard_thread.start()
            logger.info("Dashboard thread started")

            # 4. Start the scheduler's main loop (this will block)
            logger.info("Starting scheduler main loop...")
            self.is_running = True
            self.scheduler_instance.start()
            
        except Exception as e:
            logger.error(f"Service startup error: {e}", exc_info=True)
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service."""
        logger.info("Stopping Integrated Scheduler Service...")
        self.is_running = False
        if self.scheduler_instance:
            try:
                self.scheduler_instance.shutdown()
                logger.info("Scheduler stopped")
            except:
                pass
        logger.info("Service stopped")

if __name__ == '__main__':
    service = IntegratedSchedulerService()
    service.start()