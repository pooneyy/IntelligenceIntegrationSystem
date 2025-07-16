import traceback
import uuid
import logging
from typing import List

import requests
import threading
from requests import RequestException
from werkzeug.serving import make_server
from flask import Flask, request, jsonify

from GlobalConfig import *
from MyPythonUtility.ArbitraryRPC import RPCService
from MyPythonUtility.easy_config import EasyConfig
from Tools.Validation import check_sanitize_dict
from Tools.ArticleRender import default_article_render
from IntelligenceHub import CollectedData, IntelligenceHub, ProcessedData

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def common_post(url: str, data: dict, timeout: int) -> dict:
    try:
        response = requests.post(
            url,
            json=data,
            headers={'X-Request-Source': 'IntelligenceHub'},
            timeout=timeout
        )

        response.raise_for_status()
        logger.info(f"Sent request to {url} successful UUID={data['UUID']}")
        return response.json()

    except RequestException as e:
        logger.error(f"Sent request to {url} fail: {str(e)}")
        return {"status": "error", "uuid": data.get('UUID'), "reason": str(e)}

    except Exception as e:
        logger.error(f"Sent request to {url} fail: {str(e)}")
        return {"status": "error", "uuid": '', "reason": str(e)}


def post_collected_intelligence(url: str, data: CollectedData, timeout=10) -> dict:
    """
    Post collected intelligence to IntelligenceHub (/collect).
    :param url: IntelligenceHub url (without '/collect' path).
    :param data: Collector data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    if 'UUID' not in data:
        data['UUID'] = str(uuid.uuid4())
        logger.info(f"Generated new UUID: {data['UUID']}")
    validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
    if error_text:
        return {'status': 'error', 'reason': error_text}
    return common_post(f'{url}/collect', validated_data, timeout)


def post_processed_intelligence(url: str, data: ProcessedData, timeout=10) -> dict:
    """
    Post processed data to IntelligenceHub (/processed).
    :param url: IntelligenceHub url (without '/processed' path).
    :param data: Processed data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    validated_data, error_text = check_sanitize_dict(dict(data), ProcessedData)
    if error_text:
        return {'status': 'error', 'reason': error_text}
    return common_post(f'{url}/processed', validated_data, timeout)


class WebServiceAccessManager:
    def __init__(self,
                 rpc_api_token: List[str],
                 collector_token: List[str],
                 processor_token: List[str],
                 deny_on_empty_config: bool = False):
        self.rpc_api_token = rpc_api_token
        self.collector_token = collector_token
        self.processor_token = processor_token
        self.deny_on_empty_config = deny_on_empty_config

    def check_rpc_api_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_token else (token in self.rpc_api_token)

    def check_collector_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_token else (token in self.collector_token)

    def check_processor_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_token else (token in self.processor_token)


class IntelligenceHubWebService:
    def __init__(self, *,
                 serve_ip: str = '0.0.0.0',
                 serve_port: int = DEFAULT_IHUB_PORT,
                 intelligence_hub: IntelligenceHub,
                 access_manager: WebServiceAccessManager):

        # ---------------- Parameters ----------------

        self.serve_ip = serve_ip
        self.serve_port = serve_port
        self.intelligence_hub = intelligence_hub
        self.access_manager = access_manager

        # ---------------- Web Service ----------------

        self.app = Flask(__name__)
        self._setup_apis()
        self.server = make_server(serve_ip, self.serve_port, self.app)

        # ---------------- RPC Service ----------------

        self.rpc_service = RPCService(
            rpc_stub=self.intelligence_hub,
            token_checker=self.access_manager.check_rpc_api_token,
            error_handler=self.handle_error
        )

        # ----------------- Threads -----------------

        self.server_thread = threading.Thread(target=self.server.serve_forever)

    # ---------------------------------------------------- Web API -----------------------------------------------------

    def _setup_apis(self):

        @self.app.route('/api', methods=['POST'])
        def rpc_api():
            try:
                response = self.rpc_service.handle_flask_request(request)
                return response
            except Exception as e:
                    print('/api Error', e)
                    print(traceback.format_exc())
                    response = ''
            return response

        @self.app.route('/collect', methods=['POST'])
        def collect_api():
            try:
                data = dict(request.json)
                if self.access_manager.check_collector_token(data.get('token', '')):
                    result = self.intelligence_hub.submit_collected_data(data)
                    response = 'queued' if result else 'error',
                else:
                    response = 'invalid token'

                return jsonify(
                    {
                        'resp': response,
                        'uuid': data.get('UUID', '')
                    })
            except Exception as e:
                logger.error(f'collect_api() fail: {str(e)}')
                return jsonify({'resp': 'error', 'uuid': ''})

        @self.app.route('/processed', methods=['POST'])
        def feedback_api():
            try:
                data = dict(request.json)
                if self.access_manager.check_processor_token(data.get('token', '')):
                    result = self.intelligence_hub.submit_processed_data(data)
                    response = 'acknowledged' if result else 'error',
                else:
                    response = 'invalid token'

                return jsonify(
                    {
                        'resp': response,
                        'uuid': data.get('UUID', '')
                    })
            except Exception as e:
                logger.error(f'feedback_api() error: {str(e)}')
                return jsonify({'resp': 'error', 'uuid': ''})

        @self.app.route('/rssfeed.xml', methods=['GET'])
        def rssfeed_api():
            try:
                feed_xml = self.intelligence_hub.get_rssfeed()
                return feed_xml
            except Exception as e:
                logger.error(f'rssfeed_api() error: {str(e)}', stack_info=True)
                return 'Error'

        @self.app.route('/intelligence/<intelligence_uuid>', methods=['GET'])
        def intelligence_viewer_api(intelligence_uuid: str):
            intelligence = self.intelligence_hub.get_intelligence(intelligence_uuid)
            try:
                return default_article_render(intelligence)
            except Exception as e:
                logger.error(f'intelligence_viewer_api() error: {str(e)}', stack_info=True)
                return 'Error'

    # ----------------------------------------------- Startup / Shutdown -----------------------------------------------

    def startup(self):
        self.server_thread.start()

    def shutdown(self, timeout=10):
        self.server.shutdown()
        self.server_thread.join(timeout=timeout)

    # ----------------------------------------------------------------

    def handle_error(self, error: str):
        print(f'Handle error in IntelligenceHubWebService: {error}')
