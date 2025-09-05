"""
Example main application that integrates with the monitoring system.
Shows how to pass the main process PID to the monitor.
"""
import subprocess
import sys
import time
import os


def start_application():
    """Main application entry point."""
    # Get current process PID
    current_pid = os.getpid()
    print(f"Main application started with PID: {current_pid}")

    # Start monitoring system as subprocess with current PID
    monitor_process = subprocess.Popen([
        sys.executable, 'monitor_api.py',
        '--host', '0.0.0.0',
        '--port', '8080',
        '--pid', str(current_pid),
        '--add-self'
    ])

    try:
        # Main application work here
        print("Application running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            # Simulate some work
            _ = [x * x for x in range(10000)]

    except KeyboardInterrupt:
        print("Shutting down application...")
        monitor_process.terminate()
        monitor_process.wait()


if __name__ == '__main__':
    start_application()
