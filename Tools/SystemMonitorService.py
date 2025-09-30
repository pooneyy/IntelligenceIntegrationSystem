"""
System Monitoring API Module.

This module provides a RESTful web interface for monitoring system resources
and specific processes. It offers real-time statistics including CPU, memory,
disk, network usage, and process-specific metrics with thread-safe operations.

The API exposes endpoints for managing monitored processes and retrieving
statistical data in JSON format, along with a simple HTML dashboard for
quick visualization.

Key Features:
    - Real-time system and process monitoring
    - Thread-safe operations with locking mechanisms
    - Dynamic process management (add/remove at runtime)
    - RESTful API endpoints with JSON responses
    - Auto-refreshing HTML dashboard
    - Cross-platform support (Windows, Linux, macOS)

API Endpoints:
    GET    /api/stats          Retrieve complete system and process statistics
    GET    /api/system         Get system-wide statistics only
    GET    /api/processes      List all monitored processes with basic info
    GET    /api/process/<pid>  Get detailed statistics for specific process
    POST   /api/process        Add a new process to monitoring
    DELETE /api/process/<pid>  Remove a process from monitoring
    GET    /api/dashboard      HTML dashboard with auto-refresh




Usage Examples:

1. Starting the monitoring service:
   python monitor_api.py --host 0.0.0.0 --port 8000 --pid 1234 5678 --add-self

2. Adding a process to monitor:
   curl -X POST http://localhost:8000/api/process \
     -H "Content-Type: application/json" \
     -d '{"pid": 1234}'

3. Retrieving all statistics:
   curl http://localhost:8000/api/stats

4. Getting system statistics only:
   curl http://localhost:8000/api/system

5. Listing monitored processes:
   curl http://localhost:8000/api/processes

6. Removing a process from monitoring:
   curl -X DELETE http://localhost:8000/api/process/1234

7. Accessing the web dashboard:
   Open http://localhost:8000/api/dashboard in a browser

Request/Response Examples:

Add Process (POST /api/process):
  Request: {"pid": 1234}
  Success: {"status": "success", "pid": 1234}
  Error: {"error": "Could not monitor process 1234"}

Process Statistics (GET /api/process/1234):
  Response: {
    "pid": 1234,
    "name": "python",
    "cpu_percent": 12.5,
    "memory_info": {"rss": 1024000, "vms": 2048000},
    "memory_percent": 2.1,
    "num_handles": 45,
    "num_threads": 3,
    "status": "running"
  }

All Statistics (GET /api/stats):
  Response: {
    "system": {
      "cpu": {"percent": 25.0, "cores": 4},
      "memory": {"total": 17179869184, "available": 8589934592},
      "timestamp": "2023-10-15T10:30:00.000000"
    },
    "processes": {
      "1234": {
        "pid": 1234,
        "name": "python",
        "cpu_percent": 12.5
      }
    }
  }

Dependencies:
- psutil: For system and process monitoring
- flask: For web API functionality

Install required packages:
pip install psutil flask

Note: The monitoring thread runs as a daemon with a 2-second update interval.
All operations are protected with reentrant locks for thread safety.
"""

import os
import sys
import argparse
from flask import Flask, Blueprint, jsonify, request, abort

root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_path)

from SystemMonitor import SystemMonitor

DEFAULT_PORT = 8000


class MonitorAPI:
    """Web API for system monitoring data and management."""

    def __init__(self, app=None, wrapper=None, host: str = '0.0.0.0', port: int = DEFAULT_PORT, prefix: str = ''):
        """
        Initialize the monitoring API.

        Args:
            app: External Flask app instance (optional). If provided, routes will be registered to this app.
            host: Host address to bind to (used only in standalone mode)
            port: Port number to listen on (used only in standalone mode)
            prefix: URL prefix for all routes (e.g., '/monitor')
        """
        self.host = host
        self.port = port
        self.prefix = prefix.rstrip('/')
        self.monitor = SystemMonitor()
        self.wrapper = wrapper or (lambda fn: fn)

        # Create a blueprint for all monitoring routes
        self.blueprint = Blueprint('monitor', __name__)

        # Setup routes on the blueprint
        self._setup_routes()

        # Register blueprint with the provided app or create own app
        if app is not None:
            # External app mode: register blueprint to external app with prefix
            self.app = app
            app.register_blueprint(self.blueprint, url_prefix=self.prefix)
            self._is_standalone = False
        else:
            # Standalone mode: create own app and register blueprint with prefix
            self.app = Flask(__name__)
            self.app.register_blueprint(self.blueprint, url_prefix=self.prefix)
            self._is_standalone = True

    def _setup_routes(self):
        """Set up Flask routes for the API on the blueprint."""

        @self.blueprint.route('/api/stats', methods=['GET'])
        @self.wrapper
        def get_all_stats():
            """Get complete system and process statistics."""
            return jsonify(self.monitor.get_all_stats())

        @self.blueprint.route('/api/system', methods=['GET'])
        @self.wrapper
        def get_system_stats():
            """Get system-wide statistics."""
            return jsonify(self.monitor.get_system_stats())

        @self.blueprint.route('/api/processes', methods=['GET'])
        @self.wrapper
        def get_processes():
            """Get list of monitored processes."""
            return jsonify(self.monitor.get_monitored_processes())

        @self.blueprint.route('/api/process/<int:pid>', methods=['GET'])
        @self.wrapper
        def get_process_stats(pid: int):
            """Get statistics for specific process."""
            stats = self.monitor.get_process_stats(pid)
            if not stats:
                abort(404, description=f"Process {pid} not found or not monitored")
            return jsonify(stats)

        @self.blueprint.route('/api/process', methods=['POST'])
        @self.wrapper
        def add_process():
            """Add a process to monitoring."""
            data = request.get_json()
            if not data or 'pid' not in data:
                abort(400, description="PID required")

            pid = int(data['pid'])
            if self.monitor.add_process(pid):
                return jsonify({'status': 'success', 'pid': pid})
            else:
                abort(400, description=f"Could not monitor process {pid}")

        @self.blueprint.route('/api/process/<int:pid>', methods=['DELETE'])
        @self.wrapper
        def remove_process(pid: int):
            """Remove a process from monitoring."""
            if self.monitor.remove_process(pid):
                return jsonify({'status': 'success', 'pid': pid})
            else:
                abort(404, description=f"Process {pid} not found in monitoring list")

        @self.blueprint.route('/api/dashboard', methods=['GET'])
        @self.wrapper
        def get_dashboard():
            """Enhanced HTML dashboard with detailed process monitoring data."""
            stats = self.monitor.get_all_stats()

            # Format memory values for human readability
            def format_memory(bytes_value):
                if bytes_value is None:
                    return "N/A"
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.1f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.1f} TB"

            # Extract values with fallbacks for system stats
            system_data = stats.get('system', {})
            cpu_data = system_data.get('cpu', {})
            memory_data = system_data.get('memory', {})
            disk_data = system_data.get('disk', {})
            disk_usage = disk_data.get('usage', {})

            # Get values with safe fallbacks
            cpu_percent = cpu_data.get('percent', 0)
            memory_percent = memory_data.get('percent', 0)
            disk_percent = disk_usage.get('percent', 0)
            active_users = len(system_data.get('users', []))

            total_memory = memory_data.get('total', 0)
            available_memory = memory_data.get('available', 0)
            used_memory = memory_data.get('used', 0)
            free_memory = memory_data.get('free', 0)
            disk_total = disk_usage.get('total', 0)
            disk_free = disk_usage.get('free', 0)

            timestamp = stats.get('timestamp', 'Unknown')

            # Create detailed process table with safe field access
            process_rows = []
            processes = stats.get('processes', {})

            for pid, data in processes.items():
                # Extract nested data with fallbacks
                mem_info = data.get('memory_info', {})
                cpu_times = data.get('cpu_times', {})
                io_info = data.get('io_counters', {})

                # Get all values with appropriate fallbacks
                name = data.get('name', 'N/A')
                status = data.get('status', 'N/A')
                cpu_percent_val = data.get('cpu_percent', 0)
                memory_percent_val = data.get('memory_percent', 0)
                rss_memory = mem_info.get('rss', 0)
                vms_memory = mem_info.get('vms', 0)
                num_threads = data.get('num_threads', 'N/A')
                num_handles = data.get('num_handles', 'N/A')
                read_bytes = io_info.get('read_bytes', 0) // 1024
                write_bytes = io_info.get('write_bytes', 0) // 1024
                connections = data.get('connections', 0)
                user_cpu = cpu_times.get('user', 0)
                system_cpu = cpu_times.get('system', 0)

                process_rows.append(f"""
                    <tr>
                        <td>{name}</td>
                        <td>{pid}</td>
                        <td>{status}</td>
                        <td>{cpu_percent_val:.1f}%</td>
                        <td>{memory_percent_val:.1f}%</td>
                        <td>{format_memory(rss_memory)}</td>
                        <td>{format_memory(vms_memory)}</td>
                        <td>{num_threads}</td>
                        <td>{num_handles}</td>
                        <td>{read_bytes} KB</td>
                        <td>{write_bytes} KB</td>
                        <td>{connections}</td>
                        <td>{user_cpu:.1f}s</td>
                        <td>{system_cpu:.1f}s</td>
                    </tr>
                """)

            process_table = "".join(process_rows)

            base_path = self.prefix if self.prefix else ''
            stats_url = f"{base_path}/api/stats" if base_path else "/api/stats"
            system_url = f"{base_path}/api/system" if base_path else "/api/system"
            processes_url = f"{base_path}/api/processes" if base_path else "/api/processes"
            add_process_url = f"{base_path}/api/process" if base_path else "/api/process"

            return f"""
            <html>
                <head>
                    <title>Enhanced System Monitoring Dashboard</title>
                    <meta http-equiv="refresh" content="5">
                    <style>
                        body {{ 
                            font-family: Arial, sans-serif; 
                            margin: 20px;
                            background-color: #f8f9fa;
                        }}
                        .dashboard-container {{
                            max-width: 1400px;
                            margin: 0 auto;
                        }}
                        .card {{ 
                            border: 1px solid #ddd; 
                            padding: 20px; 
                            margin: 15px 0; 
                            border-radius: 8px;
                            background-color: white;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        }}
                        .system-stats {{ 
                            background-color: #e3f2fd;
                            border-left: 4px solid #2196f3;
                        }}
                        .process-stats {{ 
                            background-color: #fff3e0;
                            border-left: 4px solid #ff9800;
                        }}
                        .warning {{ 
                            color: #dc3545; 
                            font-weight: bold;
                        }}
                        .info-table {{
                            width: 100%;
                            border-collapse: collapse;
                            margin: 15px 0;
                        }}
                        .info-table th, .info-table td {{
                            padding: 12px;
                            text-align: left;
                            border-bottom: 1px solid #ddd;
                        }}
                        .info-table th {{
                            background-color: #f5f5f5;
                            font-weight: bold;
                        }}
                        .info-table tr:hover {{
                            background-color: #f8f9fa;
                        }}
                        .metric-grid {{
                            display: grid;
                            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                            gap: 15px;
                            margin: 15px 0;
                        }}
                        .metric-card {{
                            background: white;
                            padding: 15px;
                            border-radius: 6px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                            text-align: center;
                        }}
                        .metric-value {{
                            font-size: 1.5em;
                            font-weight: bold;
                            color: #2196f3;
                        }}
                        .metric-label {{
                            font-size: 0.9em;
                            color: #666;
                        }}
                    </style>
                </head>
                <body>
                    <div class="dashboard-container">
                        <h1>Enhanced System Monitoring Dashboard</h1>
                        <p>Last updated: {timestamp}</p>

                        <div class="card system-stats">
                            <h2>📊 System Statistics</h2>
                            <div class="metric-grid">
                                <div class="metric-card">
                                    <div class="metric-value">{cpu_percent}%</div>
                                    <div class="metric-label">CPU Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{memory_percent}%</div>
                                    <div class="metric-label">Memory Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{disk_percent}%</div>
                                    <div class="metric-label">Disk Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{active_users}</div>
                                    <div class="metric-label">Active Users</div>
                                </div>
                            </div>

                            <h3>Detailed System Metrics</h3>
                            <table class="info-table">
                                <tr>
                                    <th>Metric</th>
                                    <th>Value</th>
                                    <th>Metric</th>
                                    <th>Value</th>
                                </tr>
                                <tr>
                                    <td>Total Memory</td>
                                    <td>{format_memory(total_memory)}</td>
                                    <td>Available Memory</td>
                                    <td>{format_memory(available_memory)}</td>
                                </tr>
                                <tr>
                                    <td>Used Memory</td>
                                    <td>{format_memory(used_memory)}</td>
                                    <td>Free Memory</td>
                                    <td>{format_memory(free_memory)}</td>
                                </tr>
                                <tr>
                                    <td>Disk Total</td>
                                    <td>{format_memory(disk_total)}</td>
                                    <td>Disk Free</td>
                                    <td>{format_memory(disk_free)}</td>
                                </tr>
                            </table>
                        </div>

                        <div class="card process-stats">
                            <h2>🔄 Monitored Processes ({len(processes)})</h2>

                            <table class="info-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>PID</th>
                                        <th>Status</th>
                                        <th>CPU %</th>
                                        <th>Mem %</th>
                                        <th>RSS Memory</th>
                                        <th>VMS Memory</th>
                                        <th>Threads</th>
                                        <th>Handles</th>
                                        <th>Read I/O</th>
                                        <th>Write I/O</th>
                                        <th>Connections</th>
                                        <th>User CPU</th>
                                        <th>System CPU</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {process_table}
                                </tbody>
                            </table>
                        </div>

                        <div class="card">
                            <h2>⚙️ Process Management</h2>
                            <form action="{add_process_url}" method="post" style="margin: 15px 0;">
                                <input type="number" name="pid" placeholder="Enter PID" required 
                                       style="padding: 10px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <button type="submit" style="padding: 10px 20px; background-color: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                    Add Process
                                </button>
                            </form>

                            <h3>Quick Actions</h3>
                            <div style="display: flex; gap: 10px;">
                                <a href="{stats_url}" target="_blank" style="padding: 10px; background-color: #2196f3; color: white; text-decoration: none; border-radius: 4px;">
                                    View Raw JSON
                                </a>
                                <a href="{system_url}" target="_blank" style="padding: 10px; background-color: #ff9800; color: white; text-decoration: none; border-radius: 4px;">
                                    System Stats
                                </a>
                                <a href="{processes_url}" target="_blank" style="padding: 10px; background-color: #9c27b0; color: white; text-decoration: none; border-radius: 4px;">
                                    Process List
                                </a>
                            </div>
                        </div>
                    </div>
                </body>
            </html>
            """

    def start(self):
        """Start the monitoring system and web server (only in standalone mode)."""
        self.monitor.start_monitoring()
        if self._is_standalone:
            base_url = f"http://{self.host}:{self.port}{self.prefix}"
            print(f"Starting monitoring API on {base_url}")
            print(f" - Dashboard: {base_url}/api/dashboard")
            self.app.run(host=self.host, port=self.port, debug=False)
        else:
            print(f"Monitoring routes registered to external Flask application with prefix: {self.prefix}")

    def stop(self):
        """Stop the monitoring system."""
        self.monitor.stop_monitoring()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='System Monitoring API')
    parser.add_argument('--host', default='0.0.0.0', help='Host address to bind to')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port number to listen on')
    parser.add_argument('--pid', type=int, nargs='+', help='PIDs to monitor initially')
    parser.add_argument('--add-self', action='store_true', help='Add current process to monitoring')
    return parser.parse_args()


def main():
    """Main entry point for the monitoring API (standalone mode)."""
    args = parse_arguments()

    # Create MonitorAPI instance in standalone mode (no external app provided)
    api = MonitorAPI(host=args.host, port=args.port)

    # Add initial PIDs if specified
    if args.pid:
        for pid in args.pid:
            if api.monitor.add_process(pid):
                print(f"Added PID {pid} to monitoring")
            else:
                print(f"Failed to add PID {pid}")

    # Add self if requested
    if args.add_self:
        self_pid = os.getpid()
        if api.monitor.add_process(self_pid):
            print(f"Added self (PID {self_pid}) to monitoring")

    try:
        api.start()
    except KeyboardInterrupt:
        print("Shutting down monitoring system...")
        api.stop()


if __name__ == '__main__':
    main()
