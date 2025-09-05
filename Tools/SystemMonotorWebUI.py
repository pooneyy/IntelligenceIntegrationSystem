"""
Web API module for system monitoring data exposure.
Provides RESTful endpoints for monitoring data and management.
"""
import os
import sys
import argparse

from flask import Flask, jsonify, request, abort

root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_path)

from SystemMonitor import SystemMonitor


class MonitorAPI:
    """Web API for system monitoring data and management."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
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
            """Simple HTML dashboard for monitoring data."""
            stats = self.monitor.get_all_stats()
            return f"""
            <html>
                <head>
                    <title>System Monitoring Dashboard</title>
                    <meta http-equiv="refresh" content="5">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        .card {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                        .system-stats {{ background-color: #f8f9fa; }}
                        .process-stats {{ background-color: #e9ecef; }}
                        .warning {{ color: #dc3545; font-weight: bold; }}
                    </style>
                </head>
                <body>
                    <h1>System Monitoring Dashboard</h1>
                    <p>Last updated: {stats['timestamp']}</p>

                    <div class="card system-stats">
                        <h2>System Statistics</h2>
                        <p>CPU Usage: {stats['system']['cpu']['percent']}%</p>
                        <p>Memory Usage: {stats['system']['memory']['percent']}%</p>
                        <p>Disk Usage: {stats['system']['disk']['usage']['percent']}%</p>
                    </div>

                    <div class="card process-stats">
                        <h2>Monitored Processes ({len(stats['processes'])}))</h2>
                        {"".join([
                f"<div><strong>{data['name']} (PID: {pid}))</strong>: "
                f"CPU: {data['cpu_percent']}%, "
                f"Memory: {data['memory_percent']:.1f}%, "
                f"Handles: {data.get('num_handles', 'N/A')}</div>"
                for pid, data in stats['processes'].items()
            ])}
                    </div>

                    <div>
                        <h3>Manage Processes</h3>
                        <form action="/api/process" method="post">
                            <input type="number" name="pid" placeholder="Enter PID" required>
                            <button type="submit">Add Process</button>
                        </form>
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
    parser.add_argument('--port', type=int, default=8080, help='Port number to listen on')
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
