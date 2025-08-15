import os
import traceback
import uuid
import logging
from functools import wraps
from typing import List

import requests
import datetime
import threading
from werkzeug.serving import make_server
from flask import Flask, request, jsonify, session, redirect, url_for, render_template, abort

from GlobalConfig import *
from Tools.CommonPost import common_post
from MyPythonUtility.ArbitraryRPC import RPCService
from ServiceComponent.PostManager import generate_html_from_markdown
from MyPythonUtility.DictTools import check_sanitize_dict
from ServiceComponent.ArticleRender import default_article_render
from ServiceComponent.ArticleQueryRender import render_query_page
from ServiceComponent.ArticleListRender import default_article_list_render
from IntelligenceHub import CollectedData, IntelligenceHub, ProcessedData


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# def common_post(url: str, data: dict, timeout: int) -> dict:
#     try:
#         response = requests.post(
#             url,
#             json=data,
#             headers={'X-Request-Source': 'IntelligenceHub'},
#             timeout=timeout
#         )
#
#         response.raise_for_status()
#         logger.info(f"Sent request to {url} successful UUID={data['UUID']}")
#         return response.json()
#
#     except RequestException as e:
#         logger.error(f"Sent request to {url} fail: {str(e)}")
#         return {"status": "error", "uuid": data.get('UUID'), "reason": str(e)}
#
#     except Exception as e:
#         logger.error(f"Sent request to {url} fail: {str(e)}")
#         return {"status": "error", "uuid": '', "reason": str(e)}


def post_collected_intelligence(url: str, data: CollectedData, timeout=10) -> dict:
    """
    Post collected intelligence to IntelligenceHub (/collect).
    :param url: IntelligenceHub url (without '/collect' path).
    :param data: Collector data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    if not isinstance(data, CollectedData):
        return {'status': 'error', 'reason': 'Data must be CollectedData format.'}
    return common_post(f'{url}/collect', data.model_dump(exclude_unset=True), timeout)


def post_processed_intelligence(url: str, data: ProcessedData, timeout=10) -> dict:
    """
    Post processed data to IntelligenceHub (/processed).
    :param url: IntelligenceHub url (without '/processed' path).
    :param data: Processed data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    if not isinstance(data, ProcessedData):
        return {'status': 'error', 'reason': 'Data must be ProcessedData format.'}
    return common_post(f'{url}/processed', data.model_dump(exclude_unset=True), timeout)


class WebServiceAccessManager:
    def __init__(self,
                 rpc_api_tokens: List[str],
                 collector_tokens: List[str],
                 processor_tokens: List[str],
                 deny_on_empty_config: bool = False):
        self.rpc_api_tokens = rpc_api_tokens
        self.collector_tokens = collector_tokens
        self.processor_tokens = processor_tokens
        self.deny_on_empty_config = deny_on_empty_config

    def check_rpc_api_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.rpc_api_tokens)

    def check_collector_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.collector_tokens)

    def check_processor_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.processor_tokens)

    def check_user_credential(self, username: str, password: str) -> int or None:
        # TODO: Credential management
        return 1 if username == 'sleepy' and password == 'SleepySoft' else None

    @staticmethod
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or not session['logged_in']:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function


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
        self.app.secret_key = str(uuid.uuid4())
        self.app.permanent_session_lifetime = datetime.timedelta(days=7)
        self.app.config.update(
            # SESSION_COOKIE_SECURE=True,  # 仅通过HTTPS发送（生产环境必须）
            SESSION_COOKIE_HTTPONLY=True,  # 防止JavaScript访问（安全）
            SESSION_COOKIE_SAMESITE='Lax'  # 防止CSRF攻击
        )
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

        # -------------------------------------------------- Security --------------------------------------------------

        @self.app.before_request
        def refresh_session():
            session.modified = True

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form['username']
                password = request.form['password']

                user_id = self.access_manager.check_user_credential(username, password)

                if user_id:
                    session['logged_in'] = True
                    session['user_id'] = user_id
                    session['username'] = username
                    session.permanent = True
                    return redirect(url_for('show_post', article='index'))
                else:
                    return "Invalid credentials", 401
            return render_template('login.html')

        @self.app.route('/logout')
        @WebServiceAccessManager.login_required
        def logout():
            session.clear()
            return redirect(url_for('login'))

        # ---------------------------------------------- Post and Article ----------------------------------------------

        @self.app.route('/post/<path:article>')
        @WebServiceAccessManager.login_required
        def show_post(article):
            """
            Render a Markdown article as HTML with caching mechanism.

            Args:
                article: URL path of the Markdown file (relative to 'posts' directory)

            Returns:
                Rendered HTML template or 404 error
            """
            # Sanitize input and construct safe file path
            safe_article = article.replace('..', '').strip('/')  # Prevent directory traversal
            md_file_path = os.path.join('posts', f"{safe_article}.md")

            # Generate HTML from Markdown
            rendered_html_path = generate_html_from_markdown(md_file_path)

            if rendered_html_path:
                # Extract relative template path (remove 'templates/' prefix)
                template_path = os.path.relpath(
                    rendered_html_path,
                    start='templates'
                ).replace('\\', '/')  # Windows compatibility

                return render_template(template_path)
            else:
                abort(404)  # File not found or conversion failed

        # -------------------------------------------- API and Open Service --------------------------------------------

        @self.app.route('/api', methods=['POST'])
        @WebServiceAccessManager.login_required
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
                if not data.get('UUID', ''):
                    raise ValueError('Invalid UUID.')

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

        # ---------------------------------------------------- Pages ---------------------------------------------------

        @self.app.route('/rssfeed.xml', methods=['GET'])
        @WebServiceAccessManager.login_required
        def rssfeed_api():
            try:
                feed_xml = self.intelligence_hub.get_rssfeed()
                return feed_xml
            except Exception as e:
                logger.error(f'rssfeed_api() error: {str(e)}', stack_info=True)
                return 'Error'

        @self.app.route('/intelligences', methods=['GET'])
        @WebServiceAccessManager.login_required
        def intelligences_list_api():
            try:
                offset = request.args.get('offset', default=0, type=int)
                count = request.args.get('count', default=10, type=int)
                threshold = request.args.get('threshold', default=6, type=int)

                if count > 100:
                    count = 100

                intelligences, total_count = self.intelligence_hub.query_intelligence(
                    threshold = threshold, skip = offset, limit = count)
                return default_article_list_render(intelligences, offset, count, total_count)

                # total_count, _ = self.intelligence_hub.get_intelligence_summary()
                #
                # if offset < total_count:
                #     intelligences = self.intelligence_hub.get_paginated_intelligences(
                #         base_uuid=None,
                #         offset=offset,
                #         limit=count
                #     )
                #     return default_article_list_render(intelligences, offset, count, total_count)
                # else:
                #     return default_article_list_render([], offset, count, total_count)

            except Exception as e:
                logger.error(f'intelligences_list_api() error: {str(e)}', stack_info=True)
                return jsonify({"error": "Server error"}), 500

        @self.app.route('/intelligences/query', methods=['GET', 'POST'])
        @WebServiceAccessManager.login_required
        def intelligences_query_api():
            form_data = request.form if request.method == 'POST' else {}

            # Parse form data
            params = {
                'start_time': form_data.get('start_time', ''),
                'end_time': form_data.get('end_time', ''),
                'locations': form_data.get('locations', ''),
                'peoples': form_data.get('peoples', ''),
                'organizations': form_data.get('organizations', ''),
                # 'keywords': form_data.get('keywords', ''),
                'page': int(form_data.get('page', 1)),
                'per_page': int(form_data.get('per_page', 10))
            }

            # Convert to query parameters
            query_params = {}
            if params['start_time'] and params['end_time']:
                query_params['period'] = (
                    datetime.datetime.fromisoformat(params['start_time']),
                    datetime.datetime.fromisoformat(params['end_time'])
                )

            for field in ['locations', 'peoples', 'organizations']:
                if params[field]:
                    query_params[field] = [x.strip() for x in params[field].split(',')]

            # if params['keywords']:
            #     query_params['keywords'] = params['keywords']

            # Add pagination
            skip = (params['page'] - 1) * params['per_page']
            query_params.update({'skip': skip, 'limit': params['per_page']})

            # Execute query
            try:
                results, total_results = self.intelligence_hub.query_intelligence(**query_params)
                # Render HTML response
                return render_query_page(params, results, total_results)
            except Exception as e:
                error = f"Query error: {str(e)}"
                logger.error(error)
                return ''

        @self.app.route('/intelligence/<string:intelligence_uuid>', methods=['GET'])
        @WebServiceAccessManager.login_required
        def intelligence_viewer_api(intelligence_uuid: str):
            try:
                intelligence = self.intelligence_hub.get_intelligence(intelligence_uuid)
                if intelligence:
                    return default_article_render(intelligence)
                else:
                    return jsonify({"error": "Intelligence not found"}), 404
            except Exception as e:
                # logger.error(f'intelligence_viewer_api() error: {str(e)}', stack_info=True)
                print(str(e))
                traceback.print_exc()
                return jsonify({"error": "Server error"}), 500

    # ----------------------------------------------- Startup / Shutdown -----------------------------------------------

    def startup(self):
        self.server_thread.start()

    def shutdown(self, timeout=10):
        self.server.shutdown()
        self.server_thread.join(timeout=timeout)

    # ----------------------------------------------------------------

    def handle_error(self, error: str):
        print(f'Handle error in IntelligenceHubWebService: {error}')
