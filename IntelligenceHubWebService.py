import os
import traceback
import uuid
import logging
from functools import wraps
from typing import List

import datetime
import threading
from werkzeug.serving import make_server
from flask import Flask, request, jsonify, session, redirect, url_for, render_template, abort

from GlobalConfig import *
from ServiceComponent.IntelligenceHubDefines import APPENDIX_MAX_RATE_SCORE
from ServiceComponent.RateStatisticsPageRender import get_statistics_page
from ServiceComponent.UserManager import UserManager
from Tools.CommonPost import common_post
from MyPythonUtility.ArbitraryRPC import RPCService
from ServiceComponent.RSSPublisher import RSSPublisher, FeedItem
from ServiceComponent.PostManager import generate_html_from_markdown
from ServiceComponent.ArticleRender import default_article_render
from ServiceComponent.ArticleQueryRender import render_query_page
from ServiceComponent.ArticleListRender import default_article_list_render
from IntelligenceHub import CollectedData, IntelligenceHub, ProcessedData, APPENDIX_TIME_ARCHIVED

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
                 user_manager: UserManager,
                 deny_on_empty_config: bool = False):
        self.rpc_api_tokens = rpc_api_tokens
        self.collector_tokens = collector_tokens
        self.processor_tokens = processor_tokens
        self.user_manager = user_manager
        self.deny_on_empty_config = deny_on_empty_config

    def check_rpc_api_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.rpc_api_tokens)

    def check_collector_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.collector_tokens)

    def check_processor_token(self, token: str) -> bool:
        return (not self.deny_on_empty_config) if not self.rpc_api_tokens else (token in self.processor_tokens)

    def check_user_credential(self, username: str, password: str, client_ip) -> int or None:
        if self.user_manager:
            result, _ = self.user_manager.authenticate(username, password, client_ip)
            return result
        else:
            return 1 if not self.deny_on_empty_config else None

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
                 access_manager: WebServiceAccessManager,
                 rss_publisher: RSSPublisher):

        # ---------------- Parameters ----------------

        self.serve_ip = serve_ip
        self.serve_port = serve_port
        self.intelligence_hub = intelligence_hub
        self.access_manager = access_manager
        self.rss_publisher = rss_publisher

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
                client_ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                             request.headers.get('X-Real-IP', '').strip() or
                             request.remote_addr)

                username = request.form['username']
                password = request.form['password']

                user_id = self.access_manager.check_user_credential(username, password, client_ip)

                if user_id:
                    session['logged_in'] = True
                    session['user_id'] = user_id
                    session['username'] = username
                    session['login_ip'] = client_ip
                    session.permanent = True
                    return redirect(url_for('show_post', article='index'))
                else:
                    logger.info(f"Login fail - IP: {client_ip}, Username: {username}")
                    return "Invalid credentials", 401
            return render_template('login.html')

        @self.app.route('/logout')
        @WebServiceAccessManager.login_required
        def logout():
            session.clear()
            return redirect(url_for('login'))

        # ---------------------------------------------- Post and Article ----------------------------------------------

        @self.app.route('/')
        def index():
            return redirect(url_for('show_post', article='index')) \
                if session.get('logged_in') \
                else self.get_rendered_md_post('index_public') or abort(404)

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
            return self.get_rendered_md_post(article) or abort(404)

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

        @self.app.route('/manual_rate', methods=['POST'])
        def submit_rating():
            try:
                data = request.get_json()
                _uuid = data.get('uuid')
                ratings = data.get('ratings')

                self.intelligence_hub.submit_intelligence_manual_rating(_uuid, ratings)

                return jsonify({'status': 'success', 'message': 'Ratings saved'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500

        # ---------------------------------------------------- Pages ---------------------------------------------------

        @self.app.route('/rssfeed.xml', methods=['GET'])
        def rssfeed_api():
            try:
                count = request.args.get('count', default=100, type=int)
                threshold = request.args.get('threshold', default=6, type=int)

                intelligences, _ = self.intelligence_hub.query_intelligence(
                    threshold = threshold, skip = 0, limit = count)

                try:
                    rss_items = self._articles_to_rss_items(intelligences)
                    feed_xml = self.rss_publisher.generate_feed(
                        'IIS',
                        '/intelligence',
                        'IIS Processed Intelligence',
                        rss_items)
                    return feed_xml
                except Exception as e:
                    logger.error(f"Rss Feed API error: {str(e)}", stack_info=True)
                    return 'Error'
            except Exception as e:
                logger.error(f'rssfeed_api() error: {str(e)}', stack_info=True)
                return 'Error'

        @self.app.route('/intelligences', methods=['GET'])
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

        @self.app.route('/statistics/score_distribution.html', methods=['GET'])
        @WebServiceAccessManager.login_required
        def score_distribution_page():
            return get_statistics_page('/statistics/score_distribution')

    # ------------------------------------------------------------------------------------------------------------------

        @self.app.route('/statistics/score_distribution', methods=['GET', 'POST'])
        @WebServiceAccessManager.login_required
        def get_score_distribution():
            """
            API endpoint to get score distribution within a specified time range
            Expected query parameters:
            - start_time: ISO format start timestamp (e.g., '2024-01-01T00:00:00Z')
            - end_time: ISO format end timestamp (e.g., '2024-12-31T23:59:59Z')
            """
            try:
                # Get query parameters
                start_time_str = request.args.get('start_time')
                end_time_str = request.args.get('end_time')

                if not start_time_str or not end_time_str:
                    return jsonify({
                        "error": "Both start_time and end_time parameters are required"
                    }), 400

                # Convert to datetime objects
                start_time = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                end_time = datetime.datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

                # MongoDB aggregation pipeline for score distribution[4,9](@ref)
                pipeline = [
                    {
                        "$match": {
                            f"APPENDIX.{APPENDIX_TIME_ARCHIVED}": {
                                "$gte": start_time,
                                "$lte": end_time
                            },
                            f"APPENDIX.{APPENDIX_MAX_RATE_SCORE}": {
                                "$gte": 1,
                                "$lte": 10
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": f"$APPENDIX.{APPENDIX_MAX_RATE_SCORE}",
                            "count": {"$sum": 1}
                        }
                    },
                    {
                        "$sort": {"_id": 1}
                    }
                ]

                # Execute aggregation query[4](@ref)
                results = self.intelligence_hub.aggregate(pipeline)

                # Format results for frontend
                score_distribution = {str(i): 0 for i in range(1, 11)}  # Initialize all scores 1-10 with count 0

                for result in results:
                    score = str(result['_id'])
                    if score in score_distribution:
                        score_distribution[score] = result['count']

                # Convert to array format for charting
                chart_data = [
                    {"score": score, "count": count}
                    for score, count in score_distribution.items()
                ]

                return jsonify({
                    "success": True,
                    "time_range": {
                        "start": start_time_str,
                        "end": end_time_str
                    },
                    "distribution": score_distribution,
                    "chart_data": chart_data,
                    "total_records": sum(score_distribution.values())
                })

            except ValueError:
                return jsonify({
                    "error": "Invalid time format. Please use ISO format (e.g., '2024-01-01T00:00:00Z')"
                }), 400
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                return jsonify({
                    "error": "Internal server error",
                    "message": str(e)
                }), 500

    # ----------------------------------------------- Startup / Shutdown -----------------------------------------------

    def startup(self):
        self.server_thread.start()

    def shutdown(self, timeout=10):
        self.server.shutdown()
        self.server_thread.join(timeout=timeout)

    # ----------------------------------------------------------------

    def handle_error(self, error: str):
        print(f'Handle error in IntelligenceHubWebService: {error}')

    def _articles_to_rss_items(self, articles: dict | List[dict]) -> List[FeedItem]:
        # Using a fixed default time, combined with a unique UUID,
        # prevents RSS readers from mistakenly identifying article duplicates.
        default_date = datetime.datetime(1970, 1, 1)

        if not isinstance(articles, list):
            articles = [articles]
        try:
            rss_items = []
            for doc in articles:
                if 'EVENT_BRIEF' in doc and 'UUID' in doc:
                    rss_item = FeedItem(
                        guid=doc['UUID'],
                        title=doc.get('EVENT_TITLE', doc['EVENT_BRIEF']),
                        link=f"/intelligence/{doc['UUID']}",
                        description=doc['EVENT_BRIEF'],
                        pub_date=doc.get('APPENDIX', {}).get(APPENDIX_TIME_ARCHIVED, default_date))
                    rss_items.append(rss_item)
                else:
                    logger.warning(f'Warning: archived data field missing.')
            return rss_items
        except Exception as e:
            logger.error(f"Article to rss items failed: {str(e)}")
            return []

    def get_rendered_md_post(self, post_name: str) -> str:
        try:
            # Sanitize input and construct safe file path
            safe_article = post_name.replace('..', '').strip('/')  # Prevent directory traversal
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
                return ''
        except Exception as e:
            logger.error(f'Invalid post: {post_name}')
            return ''
