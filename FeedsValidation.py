import sys
import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
from xml.etree import ElementTree as ET

try:
    from flask import Flask, request, jsonify
except ImportError:
    Flask = None


# ==================== Core Validation Logic ====================
class FeedValidator:
    def __init__(self):
        self.feeds = {}  # {url: {'name': str, 'status': str}}
        self.lock = threading.Lock()
        self.status_change_callbacks = []

    def add_feeds(self, feeds_dict):
        with self.lock:
            for name, url in feeds_dict.items():
                if url not in self.feeds:
                    self.feeds[url] = {'name': name, 'status': 'unknown'}
                    self._emit_status_change(url, 'unknown')

    def validate_sync(self, url):
        self._update_status(url, 'busy')
        try:
            response = requests.get(url, timeout=10)
            valid = (response.status_code == 200 and
                     'xml' in response.headers.get('Content-Type', '') and
                     self._is_valid_rss(response.content))
            status = 'valid' if valid else 'invalid'
        except Exception:
            status = 'invalid'
        self._update_status(url, status)
        return status == 'valid'

    def validate_async(self, urls):
        def _wrapper(url):
            self.validate_sync(url)

        with ThreadPoolExecutor() as executor:
            executor.map(_wrapper, urls)

    def get_status(self, url=None):
        with self.lock:
            if url:
                return self.feeds.get(url, {}).get('status', 'unknown')
            return {url: info['status'] for url, info in self.feeds.items()}

    def clear_status(self):
        with self.lock:
            self.feeds.clear()
        for callback in self.status_change_callbacks:
            callback(None, 'cleared')

    def register_callback(self, callback):
        self.status_change_callbacks.append(callback)

    def _update_status(self, url, status):
        with self.lock:
            if url in self.feeds:
                self.feeds[url]['status'] = status
        self._emit_status_change(url, status)

    def _emit_status_change(self, url, status):
        for callback in self.status_change_callbacks:
            callback(url, status)

    @staticmethod
    def _is_valid_rss(content):
        try:
            root = ET.fromstring(content)
            return root.tag in ['rss', '{http://www.w3.org/2005/Atom}feed']
        except ET.ParseError:
            return False


# ==================== Web API Server ====================
if Flask:
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    validator_web = FeedValidator()


    @app.route('/submit', methods=['POST'])
    def web_submit():
        data = request.get_json() or {}
        feeds = data.get('feeds', {})
        validator_web.add_feeds(feeds)
        validator_web.validate_async(list(feeds.values()))
        return jsonify({"message": "Feeds submitted"}), 200


    @app.route('/status', methods=['GET'])
    def web_status():
        return jsonify(validator_web.get_status()), 200


# ==================== Command Line Interface ====================
def cmdline_validate(url):
    validator = FeedValidator()
    return 'valid' if validator.validate_sync(url) else 'invalid'


# ==================== GUI Interface ====================
def run_gui():
    try:
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                     QHBoxLayout, QTextEdit, QPushButton, QTableWidget,
                                     QTableWidgetItem, QCheckBox, QLabel, QHeaderView)
        from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
    except ImportError:
        print("PyQt5 not installed, GUI unavailable")
        return

    class ValidationWorker(QThread):
        result_ready = pyqtSignal(str, str)  # (url, status)

        def __init__(self, validator, urls):
            super().__init__()
            self.validator = validator
            self.urls = urls

        def run(self):
            for url in self.urls:
                status = 'valid' if self.validator.validate_sync(url) else 'invalid'
                self.result_ready.emit(url, status)

    class Emitter(QObject):
        status_changed = pyqtSignal(str, str)

    class FeedWindow(QMainWindow):
        def __init__(self, validator):
            super().__init__()
            self.validator = validator
            self.emitter = Emitter()
            self.workers = []
            self.init_ui()
            self.validator.register_callback(self.handle_status_change)

        def init_ui(self):
            self.setWindowTitle('Feed Validator')
            self.setGeometry(300, 300, 800, 600)

            main_widget = QWidget()
            layout = QHBoxLayout(main_widget)

            # Left Panel
            left_panel = QVBoxLayout()
            self.input_area = QTextEdit()
            self.input_area.setPlaceholderText("Enter URL or JSON...")
            self.input_area.setAcceptRichText(False)
            submit_btn = QPushButton('Submit')
            submit_btn.clicked.connect(self.handle_submit)
            left_panel.addWidget(self.input_area)
            left_panel.addWidget(submit_btn)

            # Right Panel
            right_panel = QVBoxLayout()
            self.table = QTableWidget()
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(['Select', 'Name', 'URL', 'Status'])
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

            # Control Buttons
            control_layout = QHBoxLayout()
            self.select_all_btn = QPushButton('All')
            self.select_none_btn = QPushButton('None')
            self.select_valid_btn = QPushButton('Valid')
            self.clear_invalid_btn = QPushButton('Clear Invalid')
            control_layout.addWidget(self.select_all_btn)
            control_layout.addWidget(self.select_none_btn)
            control_layout.addWidget(self.select_valid_btn)
            control_layout.addWidget(self.clear_invalid_btn)

            # JSON Output
            self.json_output = QTextEdit()
            self.json_output.setReadOnly(True)

            right_panel.addWidget(self.table)
            right_panel.addLayout(control_layout)
            right_panel.addWidget(QLabel('Selected Feeds:'))
            right_panel.addWidget(self.json_output)

            layout.addLayout(left_panel, 40)
            layout.addLayout(right_panel, 60)

            # Connect signals
            self.select_all_btn.clicked.connect(lambda: self.toggle_selection(True))
            self.select_none_btn.clicked.connect(lambda: self.toggle_selection(False))
            self.select_valid_btn.clicked.connect(self.select_valid)
            self.clear_invalid_btn.clicked.connect(self.clear_invalid)
            self.emitter.status_changed.connect(self.update_row_status)
            self.table.itemChanged.connect(self.update_json_output)

            self.setCentralWidget(main_widget)

        def handle_submit(self):
            text = self.input_area.toPlainText().strip()
            try:
                data = json.loads(text)
                feeds = data.get('feeds', {})
            except json.JSONDecodeError:
                feeds = {'User Input': text} if text else {}

            self.validator.add_feeds(feeds)
            self.populate_table(feeds)

            # 启动异步验证线程
            urls = list(feeds.values())
            worker = ValidationWorker(self.validator, urls)
            worker.result_ready.connect(self.update_status)
            worker.finished.connect(lambda: self.clean_worker(worker))
            self.workers.append(worker)
            worker.start()

        def populate_table(self, feeds):
            current_urls = set()
            for row in range(self.table.rowCount()):
                url_item = self.table.item(row, 2)
                if url_item:
                    current_urls.add(url_item.text())

            for name, url in feeds.items():
                if url not in current_urls:
                    row = self.table.rowCount()
                    self.table.insertRow(row)

                    # 添加复选框
                    checkbox = QCheckBox()
                    checkbox.setChecked(True)
                    checkbox.stateChanged.connect(self.update_json_output)
                    self.table.setCellWidget(row, 0, checkbox)

                    # 确保创建所有必要的TableWidgetItem
                    self.table.setItem(row, 1, QTableWidgetItem(name))
                    self.table.setItem(row, 2, QTableWidgetItem(url))
                    self.table.setItem(row, 3, QTableWidgetItem('unknown'))

        def update_status(self, url, status):
            for row in range(self.table.rowCount()):
                if self.table.item(row, 2).text() == url:
                    self.table.item(row, 3).setText(status)
                    break

        def clean_worker(self, worker):
            if worker in self.workers:
                self.workers.remove(worker)
            worker.deleteLater()

        def handle_status_change(self, url, status):
            self.emitter.status_changed.emit(url, status)

        def update_row_status(self, url, status):
            for row in range(self.table.rowCount()):
                if self.table.item(row, 2).text() == url:
                    self.table.item(row, 3).setText(status)

        def toggle_selection(self, state):
            for row in range(self.table.rowCount()):
                self.table.cellWidget(row, 0).setChecked(state)

        def select_valid(self):
            for row in range(self.table.rowCount()):
                status = self.table.item(row, 3).text()
                self.table.cellWidget(row, 0).setChecked(status == 'valid')

        def clear_invalid(self):
            for row in range(self.table.rowCount() - 1, -1, -1):
                if self.table.item(row, 3).text() == 'invalid':
                    self.table.removeRow(row)

        def update_json_output(self):
            selected = {}
            for row in range(self.table.rowCount()):
                # 安全获取复选框状态
                checkbox = self.table.cellWidget(row, 0)
                if not checkbox or not checkbox.isChecked():
                    continue

                # 安全获取表格项
                name_item = self.table.item(row, 1)
                url_item = self.table.item(row, 2)

                if name_item and url_item:
                    selected[name_item.text()] = url_item.text()

            self.json_output.setPlainText(json.dumps({"feeds": selected}, indent=2, ensure_ascii=False))

    validator_gui = FeedValidator()
    app = QApplication(sys.argv)
    window = FeedWindow(validator_gui)
    window.show()
    sys.exit(app.exec_())


# ==================== Main Entry Point ====================
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs='?', default=None)
    parser.add_argument('--web', action='store_true')
    args = parser.parse_args()

    if args.web:
        if not Flask:
            print("Flask not installed, web server unavailable")
            sys.exit(1)
        app.run(host='0.0.0.0', port=5000)
    elif args.url:
        print(cmdline_validate(args.url))
    else:
        run_gui()