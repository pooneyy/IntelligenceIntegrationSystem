"""
Example main application that integrates with the monitoring system.
Shows how to pass the main process PID to the monitor.
"""
import subprocess
import sys
import time
import os


root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_path)


def _run_blocking(monitor_process):
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


def start_system_monitor(
        serve_ip: str = '0.0.0.0',
        serve_port: int = 8000,
        add_self: bool = False,
        run_blocking: bool = False):

    """Main application entry point."""
    # Get current process PID
    current_pid = os.getpid()
    print(f"Main application PID: {current_pid}")

    # Start monitoring system as subprocess with current PID
    monitor_process = subprocess.Popen([
        sys.executable, os.path.join(root_path, 'SystemMonitorService.py'),
        '--host', serve_ip,
        '--port', str(serve_port),
        '--pid', str(current_pid),
        '--add-self' if add_self else ''
    ])

    return _run_blocking(monitor_process) if run_blocking else monitor_process


if __name__ == '__main__':
    start_system_monitor(run_blocking=True)
