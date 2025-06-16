# debug_service_path.py
# Debug script to check Python paths in service context

import sys
import os

# Write debug info to a file
debug_file = r'C:\SchedulerService\service_debug.txt'

with open(debug_file, 'w') as f:
    f.write("=== Service Debug Info ===\n")
    f.write(f"Python executable: {sys.executable}\n")
    f.write(f"Python version: {sys.version}\n")
    f.write(f"Current directory: {os.getcwd()}\n")
    f.write(f"\nPython path:\n")
    for p in sys.path:
        f.write(f"  {p}\n")
    f.write(f"\nEnvironment PATH:\n")
    for p in os.environ.get('PATH', '').split(os.pathsep):
        f.write(f"  {p}\n")
    
    # Check for pywin32 locations
    f.write(f"\n=== Checking pywin32 locations ===\n")
    locations = [
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'pywin32_system32'),
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'win32'),
        os.path.join(sys.prefix, 'Scripts'),
        r'C:\SchedulerService\venv\Lib\site-packages\pywin32_system32',
        r'C:\SchedulerService\venv\Lib\site-packages\win32'
    ]
    
    for loc in locations:
        f.write(f"\n{loc}:\n")
        if os.path.exists(loc):
            f.write(f"  EXISTS - Contents: {os.listdir(loc)[:5]}...\n")
        else:
            f.write(f"  NOT FOUND\n")

print(f"Debug info written to {debug_file}")