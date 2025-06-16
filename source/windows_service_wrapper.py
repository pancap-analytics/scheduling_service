# windows_service_wrapper.py
# Windows Service Wrapper for Local Scheduler Service

import sys
import os

# Only add the pywin32 DLL path to environment
pywin32_dll_path = r'C:\SchedulerService\venv\Lib\site-packages\pywin32_system32'
if os.path.exists(pywin32_dll_path):
    os.environ['PATH'] = pywin32_dll_path + os.pathsep + os.environ.get('PATH', '')

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import time
import logging

# Now import your local modules
sys.path.insert(0, r'C:\SchedulerService\source')
from local_scheduler_service import IntegratedSchedulerService

class WindowsSchedulerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PythonAnalyticsSchedulerLocal"
    _svc_display_name_ = "Python Analytics Scheduler (Local)"
    _svc_description_ = "Local task scheduler for Python analytics scripts"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
        self.service = None
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        if self.service:
            self.service.stop()
            
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()
        
    def main(self):
        # Set up logging
        log_file = r'C:\SchedulerService\logs\service.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        try:
            logging.info("Starting scheduler service")
            self.service = IntegratedSchedulerService()
            self.service.start()
            
            logging.info("Service started successfully")
            
            # Keep the service running
            while self.is_running:
                if win32event.WaitForSingleObject(self.hWaitStop, 5000) == win32event.WAIT_OBJECT_0:
                    break
                    
        except Exception as e:
            logging.error(f"Service error: {str(e)}", exc_info=True)
            servicemanager.LogErrorMsg(f"Service error: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WindowsSchedulerService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WindowsSchedulerService)