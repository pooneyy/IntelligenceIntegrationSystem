import time

from GlobalConfig import *
from IntelligenceHub import IntelligenceHub
from MyPythonUtility.easy_config import EasyConfig
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.VectorDatabase import VectorDatabase
from IntelligenceHubWebService import IntelligenceHubWebService, WebServiceAccessManager


def main():
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

        db_vector=VectorDatabase('IntelligenceIndex'),

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

    listen_ip = config.get('intelligence_hub_web_service.service.listen_ip', '0.0.0.0')
    listen_port = config.get('intelligence_hub_web_service.rpc_api.listen_port', DEFAULT_IHUB_PORT)

    rpc_api_tokens = config.get('intelligence_hub_web_service.rpc_api.tokens', [])
    collector_tokens = config.get('intelligence_hub_web_service.collector.tokens', [])
    processor_tokens = config.get('intelligence_hub_web_service.processor.tokens', [])

    access_manager = WebServiceAccessManager(
        rpc_api_tokens=rpc_api_tokens,
        collector_tokens=collector_tokens,
        processor_tokens=processor_tokens,
        deny_on_empty_config=True)

    hub_service = IntelligenceHubWebService(
        serve_ip=listen_ip,
        serve_port=listen_port,
        intelligence_hub = hub,
        access_manager=access_manager
    )
    hub_service.startup()

    # result = hub.get_intelligence('a6a485dd-d843-4acd-b58a-4d516bfb0fa8')
    # print(result)
    #
    # result = hub.query_intelligence(locations=['美国'])
    # print(result)

    prev_statistics = {}
    while True:
        if hub.statistics != prev_statistics:
            print(f'Hub queue size: {hub.statistics}')
            prev_statistics = hub.statistics
        time.sleep(2)


if __name__ == '__main__':
    main()
