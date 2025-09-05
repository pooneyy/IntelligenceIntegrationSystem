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

from flask import Flask, jsonify, request, abort

root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_path)

from SystemMonitor import SystemMonitor


DEFAULT_PORT = 8000


class MonitorAPI:
    """Web API for system monitoring data and management."""

    def __init__(self, host: str = '0.0.0.0', port: int = DEFAULT_PORT):
        """
        Initialize the monitoring API.

        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.monitor = SystemMonitor()
        self._setup_routes()

    def _setup_routes(self):
        """Set up Flask routes for the API."""

        @self.app.route('/api/stats', methods=['GET'])
        def get_all_stats():
            """Get complete system and process statistics."""
            return jsonify(self.monitor.get_all_stats())

        @self.app.route('/api/system', methods=['GET'])
        def get_system_stats():
            """Get system-wide statistics."""
            return jsonify(self.monitor.get_system_stats())

        @self.app.route('/api/processes', methods=['GET'])
        def get_processes():
            """Get list of monitored processes."""
            return jsonify(self.monitor.get_monitored_processes())

        @self.app.route('/api/process/<int:pid>', methods=['GET'])
        def get_process_stats(pid: int):
            """Get statistics for specific process."""
            stats = self.monitor.get_process_stats(pid)
            if not stats:
                abort(404, description=f"Process {pid} not found or not monitored")
            return jsonify(stats)

        @self.app.route('/api/process', methods=['POST'])
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

        @self.app.route('/api/process/<int:pid>', methods=['DELETE'])
        def remove_process(pid: int):
            """Remove a process from monitoring."""
            if self.monitor.remove_process(pid):
                return jsonify({'status': 'success', 'pid': pid})
            else:
                abort(404, description=f"Process {pid} not found in monitoring list")

        @self.app.route('/api/dashboard', methods=['GET'])
        def get_dashboard():
            """Enhanced HTML dashboard with detailed process monitoring data."""
            stats = self.monitor.get_all_stats()

            # Format memory values for human readability
            def format_memory(bytes_value):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.1f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.1f} TB"

            # Create detailed process table
            process_rows = []
            for pid, data in stats['processes'].items():
                mem_info = data.get('memory_info', {})
                cpu_times = data.get('cpu_times', {})
                io_info = data.get('io_counters', {})

                process_rows.append(f"""
                    <tr>
                        <td>{data.get('name', 'N/A')}</td>
                        <td>{pid}</td>
                        <td>{data.get('status', 'N/A')}</td>
                        <td>{data.get('cpu_percent', 0):.1f}%</td>
                        <td>{data.get('memory_percent', 0):.1f}%</td>
                        <td>{format_memory(mem_info.get('rss', 0))}</td>
                        <td>{format_memory(mem_info.get('vms', 0))}</td>
                        <td>{data.get('num_threads', 'N/A')}</td>
                        <td>{data.get('num_handles', 'N/A')}</td>
                        <td>{io_info.get('read_bytes', 0) // 1024} KB</td>
                        <td>{io_info.get('write_bytes', 0) // 1024} KB</td>
                        <td>{data.get('connections', 0)}</td>
                        <td>{cpu_times.get('user', 0):.1f}s</td>
                        <td>{cpu_times.get('system', 0):.1f}s</td>
                    </tr>
                """)

            process_table = "".join(process_rows)

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
                        <p>Last updated: {stats['timestamp']}</p>

                        <div class="card system-stats">
                            <h2>📊 System Statistics</h2>
                            <div class="metric-grid">
                                <div class="metric-card">
                                    <div class="metric-value">{stats['system']['cpu']['percent']}%</div>
                                    <div class="metric-label">CPU Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{stats['system']['memory']['percent']}%</div>
                                    <div class="metric-label">Memory Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{stats['system']['disk']['usage']['percent']}%</div>
                                    <div class="metric-label">Disk Usage</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{len(stats['system'].get('users', []))}</div>
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
                                    <td>{format_memory(stats['system']['memory']['total'])}</td>
                                    <td>Available Memory</td>
                                    <td>{format_memory(stats['system']['memory']['available'])}</td>
                                </tr>
                                <tr>
                                    <td>Used Memory</td>
                                    <td>{format_memory(stats['system']['memory']['used'])}</td>
                                    <td>Free Memory</td>
                                    <td>{format_memory(stats['system']['memory']['free'])}</td>
                                </tr>
                                <tr>
                                    <td>Disk Total</td>
                                    <td>{format_memory(stats['system']['disk']['usage']['total'])}</td>
                                    <td>Disk Free</td>
                                    <td>{format_memory(stats['system']['disk']['usage']['free'])}</td>
                                </tr>
                            </table>
                        </div>

                        <div class="card process-stats">
                            <h2>🔄 Monitored Processes ({len(stats['processes'])})</h2>

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
                            <form action="/api/process" method="post" style="margin: 15px 0;">
                                <input type="number" name="pid" placeholder="Enter PID" required 
                                       style="padding: 10px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <button type="submit" style="padding: 10px 20px; background-color: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                    Add Process
                                </button>
                            </form>

                            <h3>Quick Actions</h3>
                            <div style="display: flex; gap: 10px;">
                                <a href="/api/stats" target="_blank" style="padding: 10px; background-color: #2196f3; color: white; text-decoration: none; border-radius: 4px;">
                                    View Raw JSON
                                </a>
                                <a href="/api/system" target="_blank" style="padding: 10px; background-color: #ff9800; color: white; text-decoration: none; border-radius: 4px;">
                                    System Stats
                                </a>
                                <a href="/api/processes" target="_blank" style="padding: 10px; background-color: #9c27b0; color: white; text-decoration: none; border-radius: 4px;">
                                    Process List
                                </a>
                            </div>
                        </div>
                    </div>
                </body>
            </html>
            """

    def start(self):
        """Start the monitoring system and web server."""
        self.monitor.start_monitoring()
        print(f"Starting monitoring API on http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False)

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
    """Main entry point for the monitoring API."""
    args = parse_arguments()

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
        import os
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
