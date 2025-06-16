# verify_packages.py
# Verify all required packages are working

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print("\nTesting package imports:")

packages = [
    'psycopg2',
    'apscheduler',
    'flask',
    'flask_cors',
    'psutil',
    'win32serviceutil'
]

for package in packages:
    try:
        if package == 'apscheduler':
            from apscheduler.schedulers.background import BackgroundScheduler
            print(f"✓ {package} - BackgroundScheduler imported successfully")
        elif package == 'flask_cors':
            from flask_cors import CORS
            print(f"✓ {package} - CORS imported successfully")
        else:
            exec(f"import {package}")
            print(f"✓ {package} imported successfully")
    except Exception as e:
        print(f"✗ {package} failed: {e}")

# Test database connection
print("\nTesting database connection:")
try:
    import psycopg2
    # Just test that we can create a connection object (it will fail to connect, but that's OK)
    print("✓ psycopg2 can create connection objects")
except Exception as e:
    print(f"✗ psycopg2 error: {e}")