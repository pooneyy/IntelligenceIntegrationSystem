import time
import uuid
import datetime
import traceback
from flask import Flask
from typing import Tuple

from GlobalConfig import *
from IntelligenceHub import IntelligenceHub
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.SystemMonotorLauncher import start_system_monitor
from PyLoggingBackend import setup_logging, LoggerBackend
from MyPythonUtility.easy_config import EasyConfig
from ServiceComponent.UserManager import UserManager
from ServiceComponent.RSSPublisher import RSSPublisher
# from Tools.VectorDatabase import VectorDatabase
from IntelligenceHubWebService import IntelligenceHubWebService, WebServiceAccessManager


wsgi_app = Flask(__name__)
wsgi_app.secret_key = str(uuid.uuid4())
wsgi_app.permanent_session_lifetime = datetime.timedelta(days=7)
wsgi_app.config.update(
    # SESSION_COOKIE_SECURE=True,  # 仅通过HTTPS发送（生产环境必须）
    SESSION_COOKIE_HTTPONLY=True,  # 防止JavaScript访问（安全）
    SESSION_COOKIE_SAMESITE='Lax'  # 防止CSRF攻击
)


def show_intelligence_hub_statistics_forever(hub: IntelligenceHub):
    prev_statistics = {}
    while True:
        if hub.statistics != prev_statistics:
            print(f'Hub queue size: {hub.statistics}')
            prev_statistics = hub.statistics
        time.sleep(2)


def start_intelligence_hub_service() -> Tuple[IntelligenceHub, IntelligenceHubWebService]:
    config = EasyConfig()

    print('Apply config: ')
    print(config.dump_text())

    ai_service_url = config.get('intelligence_hub.ai_service.url', OPEN_AI_API_BASE_URL_SELECT)
    ai_service_token = config.get('intelligence_hub.ai_service.token', 'Sleepy')
    ai_service_model = config.get('intelligence_hub.ai_service.model', MODEL_SELECT)

    api_client = OpenAICompatibleAPI(
        api_base_url=ai_service_url,
        token=ai_service_token,
        default_model=ai_service_model)

    ref_host_url = config.get('intelligence_hub_web_service.service.host_url', 'http://127.0.0.1:5000')

    mongodb_host = config.get('mongodb.host', 'localhost')
    mongodb_port = config.get('mongodb.port', 27017)
    mongodb_user = config.get('mongodb.user', '')
    mongodb_pass = config.get('mongodb.password', '')

    hub = IntelligenceHub(
        ref_url=ref_host_url,

        # db_vector=VectorDatabase('IntelligenceIndex'),

        db_cache=MongoDBStorage(
            host=mongodb_host,
            port=mongodb_port,
            username=mongodb_user,
            password=mongodb_pass,
            collection_name='intelligence_cached'),

        db_archive=MongoDBStorage(
            host=mongodb_host,
            port=mongodb_port,
            username=mongodb_user,
            password=mongodb_pass,
            collection_name='intelligence_archived'),

        ai_client = api_client
    )
    hub.startup()

    rpc_api_tokens = config.get('intelligence_hub_web_service.rpc_api.tokens', [])
    collector_tokens = config.get('intelligence_hub_web_service.collector.tokens', [])
    processor_tokens = config.get('intelligence_hub_web_service.processor.tokens', [])

    rss_base_url = config.get('intelligence_hub_web_service.rss.host_prefix', 'http://127.0.0.1:5000')

    access_manager = WebServiceAccessManager(
        rpc_api_tokens=rpc_api_tokens,
        collector_tokens=collector_tokens,
        processor_tokens=processor_tokens,
        user_manager=UserManager(DEFAULT_USER_DB_PATH),
        deny_on_empty_config=True)

    hub_service = IntelligenceHubWebService(
        intelligence_hub = hub,
        access_manager=access_manager,
        rss_publisher=RSSPublisher(rss_base_url)
    )

    hub_service.register_routers(wsgi_app)

    return hub, hub_service


# ----------------------------------------------------------------------------------------------------------------------

def run():
    log_file = 'iis.log'
    setup_logging(log_file)

    ihub, ihub_service = start_intelligence_hub_service()

    log_backend = LoggerBackend(monitoring_file_path=log_file, cache_limit_count=100000)
    log_backend.register_router(app=wsgi_app, wrapper=ihub_service.access_manager.login_required)

    start_system_monitor()


try:
    run()
except Exception as e:
    print(str(e))
    print(traceback.format_exc())
finally:
    pass
