import time

from GlobalConfig import *
from IntelligenceHub import IntelligenceHub
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.VectorDatabase import VectorDatabase
from IntelligenceHubWebService import IntelligenceHubWebService


def main():
    api_client = OpenAICompatibleAPI(
        api_base_url=OPEN_AI_API_BASE_URL_SELECT,
        token='Sleepy',
        default_model=MODEL_SELECT)

    hub = IntelligenceHub(
        ref_url='http://127.0.0.1:5000',
        db_vector=VectorDatabase('IntelligenceIndex'),
        db_cache=MongoDBStorage(collection_name='intelligence_cached'),
        db_archive=MongoDBStorage(collection_name='intelligence_archived'),
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
