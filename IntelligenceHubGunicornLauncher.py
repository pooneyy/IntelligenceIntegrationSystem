#!/usr/bin/env python3
"""
Gunicorn进程启动与监控脚本
功能：使用Gunicorn启动IntelligenceHubLauncher应用，监控其健康状态，并在必要时自动重启。
注意：Gunicorn本身不支持Windows平台，请在Linux或macOS下运行此脚本。
"""

import os
import sys
import time
import json
import logging
import subprocess
import requests
from datetime import datetime, timedelta

# ==================== 配置区域 (根据你的需求修改这些参数) ====================
# Gunicorn启动参数
GUNICORN_CMD = [
    "gunicorn",
    "-b", "0.0.0.0:5000",  # 绑定地址和端口
    "-w", "1",  # worker进程数
    "-k", "gevent",  # worker类型
    "--access-logfile", "./access.log",
    "--error-logfile", "./error.log",
    "--pythonpath", ".",  # 确保Python路径包含当前目录
    "IntelligenceHubLauncher:app"  # 应用模块和应用实例名
]

# 健康检查配置
HEALTH_CHECK_URL = "http://127.0.0.1:5000/maintenance/ping"  # 健康检查URL
HEALTH_CHECK_TIMEOUT = 10  # 请求超时时间(秒)
CHECK_INTERVAL = 30  # 健康检查间隔(秒)
RESTART_COOL_DOWN = 5 * 60

# 重启配置
MAX_RESTART_ATTEMPTS = 5  # 最大重启尝试次数
RESTART_COOLDOWN = 300  # 重启冷却时间(秒)，防止频繁重启(5分钟)

# 日志配置
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = "./gunicorn_manager.log"


# ==================== 脚本主逻辑 (以下代码一般不需要修改) ====================

class GunicornManager:
    def __init__(self):
        self.process = None
        self.pid = None
        self.restart_count = 0
        self.last_restart_time = 0
        self.setup_logging()

    def setup_logging(self):
        """配置日志记录"""
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
        """启动Gunicorn进程"""
        try:
            self.logger.info("正在启动Gunicorn服务...")
            self.logger.info(f"启动命令: {' '.join(GUNICORN_CMD)}")

            # 启动Gunicorn进程
            self.process = subprocess.Popen(
                GUNICORN_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.pid = self.process.pid
            self.logger.info(f"Gunicorn启动成功，PID: {self.pid}")

            # 等待一段时间让服务完全启动
            time.sleep(5)
            return True

        except Exception as e:
            self.logger.error(f"启动Gunicorn失败: {str(e)}")
            return False

    def check_health(self):
        """检查服务健康状态"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=HEALTH_CHECK_TIMEOUT)
            if response.status_code == 200:
                self.logger.debug("健康检查成功")
                return True
            else:
                self.logger.warning(f"健康检查返回非200状态码: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.warning(f"健康检查请求失败: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"健康检查发生未知错误: {str(e)}")
            return False

    def restart_gunicorn(self):
        """重启Gunicorn进程"""
        current_time = time.time()

        # 检查是否在冷却期内
        if current_time - self.last_restart_time < RESTART_COOL_DOWN:
            remaining = int(RESTART_COOL_DOWN - (current_time - self.last_restart_time))
            self.logger.warning(f"仍在重启冷却期内，{remaining}秒后可重启")
            return False

        # 检查是否超过最大重启次数
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            self.logger.error(f"已达到最大重启次数({MAX_RESTART_ATTEMPTS})，不再尝试重启")
            return False

        self.logger.info("尝试重启Gunicorn服务...")

        # 先终止现有进程
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                self.logger.info("原有进程已终止")
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.logger.warning("进程强制终止")
                except Exception as e:
                    self.logger.error(f"终止进程失败: {str(e)}")
            except Exception as e:
                self.logger.error(f"终止进程时发生错误: {str(e)}")

        # 启动新进程
        success = self.start_gunicorn()
        if success:
            self.restart_count += 1
            self.last_restart_time = current_time
            self.logger.info(f"重启成功，这是第{self.restart_count}次重启")
        else:
            self.logger.error("重启失败")

        return success

    def run(self):
        """主运行循环"""
        self.logger.info("Gunicorn管理脚本启动")
        self.logger.info(f"健康检查URL: {HEALTH_CHECK_URL}")
        self.logger.info(f"检查间隔: {CHECK_INTERVAL}秒")
        self.logger.info(f"最大重启次数: {MAX_RESTART_ATTEMPTS}")
        self.logger.info(f"重启冷却时间: {RESTART_COOL_DOWN}秒")

        # 初始启动
        if not self.start_gunicorn():
            self.logger.error("初始启动失败，脚本退出")
            return

        # 主监控循环
        try:
            while True:
                # 检查进程是否仍在运行
                if self.process.poll() is not None:
                    exit_code = self.process.poll()
                    self.logger.error(f"Gunicorn进程已退出，返回值: {exit_code}")
                    self.restart_gunicorn()
                    continue

                # 健康检查
                if not self.check_health():
                    self.logger.warning("健康检查失败，尝试重启服务")
                    self.restart_gunicorn()

                # 等待下一次检查
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止服务...")
        except Exception as e:
            self.logger.error(f"监控循环发生未知错误: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        self.logger.info("正在清理资源...")
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                self.logger.info("Gunicorn进程已正常终止")
            except:
                try:
                    self.process.kill()
                    self.logger.info("Gunicorn进程已强制终止")
                except:
                    self.logger.error("无法终止Gunicorn进程")
        self.logger.info("脚本退出")


if __name__ == "__main__":
    manager = GunicornManager()
    manager.run()
