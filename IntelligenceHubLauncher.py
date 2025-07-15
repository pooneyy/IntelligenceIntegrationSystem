import time

from GlobalConfig import *
from IntelligenceHub import IntelligenceHub
from MyPythonUtility.easy_config import EasyConfig
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.VectorDatabase import VectorDatabase
from IntelligenceHubWebService import IntelligenceHubWebService


def main():
    config = EasyConfig()

    ai_service_url = config.get('intelligence_hub.ai_service.url', OPEN_AI_API_BASE_URL_SELECT)
    ai_service_token = config.get('intelligence_hub.ai_service.token', 'Sleepy')
    ai_service_model = config.get('intelligence_hub.ai_service.model', MODEL_SELECT)

    api_client = OpenAICompatibleAPI(
        api_base_url=ai_service_url,
        token=ai_service_token,
        default_model=ai_service_model)

    ref_host_url = config.get('intelligence_hub_web_service.service.host_access_url', 'http://127.0.0.1:5000')
    mongodb_url = config.get('mongodb.url', 'mongodb://localhost:27017/')
    mongodb_user = config.get('mongodb.user', '')
    mongodb_pass = config.get('mongodb.password', '')

    hub = IntelligenceHub(
        ref_url=ref_host_url,

        db_vector=VectorDatabase('IntelligenceIndex'),

        db_cache=MongoDBStorage(
            mongodb_url=mongodb_url,
            mongodb_user=mongodb_user,
            mongodb_pass=mongodb_pass,
            collection_name='intelligence_cached'),

        db_archive=MongoDBStorage(
            mongodb_url=mongodb_url,
            mongodb_user=mongodb_user,
            mongodb_pass=mongodb_pass,
            collection_name='intelligence_archived'),

        ai_client = api_client
    )
    hub.startup()

    hub_service = IntelligenceHubWebService(
        intelligence_hub = hub
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
