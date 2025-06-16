# test_installation.py
"""
Test script for local scheduler installation.
"""

import sys
import os
from pathlib import Path

def test_python_environment():
    """Test the Python environment."""
    print("=== Python Environment Test ===")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Virtual environment: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    print()
    return True

def test_pywin32():
    """Test pywin32 modules."""
    print("=== pywin32 Test ===")
    try:
        import win32service
        import win32serviceutil
        import servicemanager
        print("SUCCESS: All pywin32 modules imported successfully")
        return True
    except ImportError as e:
        print(f"ERROR: pywin32 import failed: {e}")
        return False

def test_required_packages():
    """Test required packages."""
    print("\n=== Required Packages Test ===")
    
    packages = [
        'psycopg2',
        'apscheduler',
        'flask',
        'flask_cors',
        'psutil'
    ]
    
    all_good = True
    for package in packages:
        try:
            __import__(package)
            print(f"OK {package}")
        except ImportError:
            print(f"ERROR {package} - not available")
            all_good = False
    
    return all_good

def test_database_connection():
    """Test database connection."""
    print("\n=== Database Connection Test ===")
    
    try:
        # Add current directory to path to import local config
        sys.path.insert(0, '.')
        
        import production_config_local as config
        print(f"OK Config loaded")
        print(f"   Database host: {config.DATABASE_CONFIG['host']}")
        print(f"   Database name: {config.DATABASE_CONFIG['database']}")
        
        import psycopg2
        conn = psycopg2.connect(**config.DATABASE_CONFIG)
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"OK Database connected")
        print(f"   PostgreSQL: {version.split(',')[0]}")
        
        # Test schema
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = %s
        """, (config.DATABASE_SCHEMA,))
        table_count = cursor.fetchone()[0]
        print(f"   Schema '{config.DATABASE_SCHEMA}': {table_count} tables")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR Database connection failed: {e}")
        return False

def test_service_modules():
    """Test service module imports."""
    print("\n=== Service Modules Test ===")
    
    try:
        from local_scheduler_service import IntegratedSchedulerService
        print("OK local_scheduler_service imported")
        
        from windows_service_wrapper import LocalSchedulerWindowsService
        print("OK windows_service_wrapper imported")
        
        from monitoring_dashboard import app
        print("OK monitoring_dashboard imported")
        
        # Test if db_models works
        from db_models import DatabaseManager
        print("OK db_models imported")
        
        return True
        
    except Exception as e:
        print(f"ERROR Service module import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_management():
    """Test task management CLI."""
    print("\n=== Task Management Test ===")
    
    try:
        from task_management_cli import TaskManagementCLI
        print("OK task_management_cli imported")
        return True
    except Exception as e:
        print(f"ERROR Task management import failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Local Scheduler Installation Test")
    print("=" * 50)
    
    tests = [
        ("Python Environment", test_python_environment),
        ("pywin32 Modules", test_pywin32),
        ("Required Packages", test_required_packages),
        ("Database Connection", test_database_connection),
        ("Service Modules", test_service_modules),
        ("Task Management", test_task_management)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\nERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("\nSUCCESS: All tests passed!")
        print("\nYou can now install the Windows service:")
        print("  C:\\SchedulerService\\install_service.bat (run as Administrator)")
    else:
        print(f"\nWARNING: {len(results) - passed} test(s) failed")
        print("Please fix the issues before installing the service.")
        
        # Provide specific guidance
        failed_tests = [name for name, result in results if not result]
        if "Database Connection" in failed_tests:
            print("\nDatabase connection issues:")
            print("- Check that PostgreSQL is running")
            print("- Verify network connectivity")
            print("- Check credentials in production_config_local.py")
        
        if "Service Modules" in failed_tests:
            print("\nService module issues:")
            print("- Ensure all 5 Python files are created in C:\\SchedulerService\\source\\")
            print("- Check for syntax errors in the Python files")
        
        if "pywin32 Modules" in failed_tests:
            print("\npywin32 issues:")
            print("- Try reinstalling: pip install --force-reinstall pywin32")
            print("- Run as Administrator: python Scripts/pywin32_postinstall.py -install")

if __name__ == '__main__':
    main()
    input("\nPress Enter to exit...")