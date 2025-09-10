#!/usr/bin/env python3
"""
Gunicorn Process Management and Monitoring Script
Function: Starts the IntelligenceHubLauncher application using Gunicorn, monitors its health status,
          and automatically restarts when necessary.
Note: Gunicorn itself does not support Windows platform. Please run this script on Linux or macOS.
"""

import os
import sys
import time
import logging
import subprocess
import requests


# ==================== CONFIGURATION SECTION (Modify these parameters as needed) ====================
# Gunicorn startup parameters
GUNICORN_CMD = [
    "gunicorn",
    "-b", "0.0.0.0:5000",  # Bind address and port
    "-w", "1",  # Number of worker processes
    "-k", "gevent",  # Worker type
    "--access-logfile", "./access.log",
    "--error-logfile", "./error.log",
    "--pythonpath", ".",  # Ensure Python path includes current directory
    "IntelligenceHubStartup:wsgi_app"  # Application module and application instance name
]

# Health check configuration
HEALTH_CHECK_URL = "http://127.0.0.1:5000/maintenance/ping"  # Health check URL
HEALTH_CHECK_TIMEOUT = 10  # Request timeout (seconds)
CHECK_INTERVAL = 30  # Health check interval (seconds)
RESTART_COOL_DOWN = 5 * 60

# Restart configuration
MAX_RESTART_ATTEMPTS = 5  # Maximum restart attempts
RESTART_COOLDOWN = 300  # Restart cooldown time (seconds) to prevent frequent restarts (5 minutes)

# Log configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = "./gunicorn_manager.log"


class GunicornManager:
    def __init__(self):
        self.process = None
        self.pid = None
        self.restart_count = 0
        self.last_restart_time = 0
        self.setup_logging()

    def setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("GunicornManager")

    def start_gunicorn(self):
        """Start Gunicorn process"""
        try:
            self.logger.info("Starting Gunicorn service...")
            self.logger.info(f"Start command: {' '.join(GUNICORN_CMD)}")

            # Start Gunicorn process
            self.process = subprocess.Popen(
                GUNICORN_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.pid = self.process.pid
            self.logger.info(f"Gunicorn started successfully, PID: {self.pid}")

            # Wait for a while to allow the service to fully start up
            time.sleep(5)
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Gunicorn: {str(e)}")
            return False

    def check_health(self):
        """Check service health status"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=HEALTH_CHECK_TIMEOUT)
            if response.status_code == 200:
                self.logger.debug("Health check successful")
                return True
            else:
                self.logger.warning(f"Health check returned non-200 status code: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Health check request failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unknown error occurred during health check: {str(e)}")
            return False

    def restart_gunicorn(self):
        """Restart Gunicorn process"""
        current_time = time.time()

        # Check if within cooldown period
        if current_time - self.last_restart_time < RESTART_COOL_DOWN:
            remaining = int(RESTART_COOL_DOWN - (current_time - self.last_restart_time))
            self.logger.warning(f"Still within restart cooldown period, can restart in {remaining} seconds")
            return False

        # Check if maximum restart attempts exceeded
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            self.logger.error(f"Maximum restart attempts ({MAX_RESTART_ATTEMPTS}) reached, no further attempts")
            return False

        self.logger.info("Attempting to restart Gunicorn service...")

        # First terminate existing process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                self.logger.info("Original process terminated")
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.logger.warning("Process forcibly terminated")
                except Exception as e:
                    self.logger.error(f"Failed to kill process: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error occurred while terminating process: {str(e)}")

        # Start new process
        success = self.start_gunicorn()
        if success:
            self.restart_count += 1
            self.last_restart_time = current_time
            self.logger.info(f"Restart successful, this is the {self.restart_count}th restart")
        else:
            self.logger.error("Restart failed")

        return success

    def run(self):
        """Main run loop"""
        self.logger.info("Gunicorn management script starting")
        self.logger.info(f"Health check URL: {HEALTH_CHECK_URL}")
        self.logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
        self.logger.info(f"Maximum restart attempts: {MAX_RESTART_ATTEMPTS}")
        self.logger.info(f"Restart cooldown time: {RESTART_COOL_DOWN} seconds")

        # Initial startup
        if not self.start_gunicorn():
            self.logger.error("Initial startup failed, script exiting")
            return

        # Main monitoring loop
        try:
            while True:
                # Check if process is still running
                if self.process.poll() is not None:
                    exit_code = self.process.poll()
                    self.logger.error(f"Gunicorn process has exited, return value: {exit_code}")
                    self.restart_gunicorn()
                    continue

                # # Health check
                # if not self.check_health():
                #     self.logger.warning("Health check failed, attempting to restart service")
                #     self.restart_gunicorn()

                # Wait for next check
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            self.logger.info("Interrupt signal received, stopping service...")
        except Exception as e:
            self.logger.error(f"Unknown error occurred in monitoring loop: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up resources...")
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                self.logger.info("Gunicorn process terminated normally")
            except:
                try:
                    self.process.kill()
                    self.logger.info("Gunicorn process forcibly terminated")
                except:
                    self.logger.error("Unable to terminate Gunicorn process")
        self.logger.info("Script exiting")


if __name__ == "__main__":
    manager = GunicornManager()
    manager.run()
