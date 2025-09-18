import re
import logging
import pymongo
import datetime
from flask import jsonify
from typing import Optional, List, Tuple, Union, Dict, Any

from Tools.MongoDBAccess import MongoDBStorage
from ServiceComponent.IntelligenceHubDefines import APPENDIX_TIME_ARCHIVED, APPENDIX_MAX_RATE_SCORE

logger = logging.getLogger(__name__)


class IntelligenceStatisticsEngine:
    def __init__(self, db: MongoDBStorage):
        self.__mongo_db = db

    def get_score_distribution(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """
        API endpoint to get score distribution within a specified time range
        Expected query parameters:
        - start_time: ISO format start timestamp (e.g., '2024-01-01T00:00:00Z')
        - end_time: ISO format end timestamp (e.g., '2024-12-31T23:59:59Z')
        """
        # try:

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
        collection = self.__mongo_db.collection
        results = collection.aggregate(pipeline)

        # Format results for frontend
        score_distribution = {str(i): 0 for i in range(1, 11)}  # Initialize all scores 1-10 with count 0

        for result in results:
            score = str(result['_id'])
            if score in score_distribution:
                score_distribution[score] = result['count']

        return score_distribution

            # # Convert to array format for charting
            # chart_data = [
            #     {"score": score, "count": count}
            #     for score, count in score_distribution.items()
            # ]
            #
            # return jsonify({
            #     "success": True,
            #     "time_range": {
            #         "start": start_time.strftime(),
            #         "end": start_time.strftime(),
            #     },
            #     "distribution": score_distribution,
            #     "chart_data": chart_data,
            #     "total_records": sum(score_distribution.values())
            # })

        # except ValueError:
        #     return jsonify({
        #         "error": "Invalid time format. Please use ISO format (e.g., '2024-01-01T00:00:00Z')"
        #     }), 400
        # except Exception as e:
        #     logger.error(f"Error processing request: {str(e)}")
        #     return jsonify({
        #         "error": "Internal server error",
        #         "message": str(e)
        #     }), 500

    def get_hourly_stats(self, start_time: datetime.datetime, end_time: datetime.datetime) -> list:
        """Get record counts grouped by hour for the specified time range"""
        # MongoDB aggregation pipeline for hourly statistics
        pipeline = [
            {
                "$match": {
                    "APPENDIX.__TIME_ARCHIVED__": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$APPENDIX.__TIME_ARCHIVED__"},
                        "month": {"$month": "$APPENDIX.__TIME_ARCHIVED__"},
                        "day": {"$dayOfMonth": "$APPENDIX.__TIME_ARCHIVED__"},
                        "hour": {"$hour": "$APPENDIX.__TIME_ARCHIVED__"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1,
                    "_id.day": 1,
                    "_id.hour": 1
                }
            }
        ]

        collection = self.__mongo_db.collection
        return list(collection.aggregate(pipeline))

        # result = list(collection.aggregate(pipeline))
        # return jsonify(result)

    def get_daily_stats(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Get record counts grouped by day for the specified time range"""
        # MongoDB aggregation pipeline for daily statistics
        pipeline = [
            {
                "$match": {
                    "APPENDIX.__TIME_ARCHIVED__": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$APPENDIX.__TIME_ARCHIVED__"},
                        "month": {"$month": "$APPENDIX.__TIME_ARCHIVED__"},
                        "day": {"$dayOfMonth": "$APPENDIX.__TIME_ARCHIVED__"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1,
                    "_id.day": 1
                }
            }
        ]

        collection = self.__mongo_db.collection
        return list(collection.aggregate(pipeline))

        # return jsonify(result)

    def get_weekly_stats(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Get record counts grouped by week for the specified time range"""
        # MongoDB aggregation pipeline for weekly statistics
        pipeline = [
            {
                "$match": {
                    "APPENDIX.__TIME_ARCHIVED__": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$APPENDIX.__TIME_ARCHIVED__"},
                        "week": {"$week": "$APPENDIX.__TIME_ARCHIVED__"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.week": 1
                }
            }
        ]

        collection = self.__mongo_db.collection
        return list(collection.aggregate(pipeline))

        # return jsonify(result)

    def get_monthly_stats(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Get record counts grouped by month for the specified time range"""
        # MongoDB aggregation pipeline for monthly statistics
        pipeline = [
            {
                "$match": {
                    "APPENDIX.__TIME_ARCHIVED__": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$APPENDIX.__TIME_ARCHIVED__"},
                        "month": {"$month": "$APPENDIX.__TIME_ARCHIVED__"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1
                }
            }
        ]

        collection = self.__mongo_db.collection
        return list(collection.aggregate(pipeline))

        # return jsonify(result)

    def get_stats_summary(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Get overall statistics for the specified time range"""
        collection = self.__mongo_db.collection

        # Total count in time range
        total_count = self.__mongo_db.collection.count_documents({
            "APPENDIX.__TIME_ARCHIVED__": {
                "$gte": start_time,
                "$lte": end_time
            }
        })

        # Count by informant
        informant_pipeline = [
            {
                "$match": {
                    "APPENDIX.__TIME_ARCHIVED__": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": "$INFORMANT",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": 10  # Top 10 informants
            }
        ]

        informant_stats = list(collection.aggregate(informant_pipeline))
        return informant_stats

        # return jsonify({
        #     "total_count": total_count,
        #     "time_range": {
        #         "start": start_time,
        #         "end": end_time
        #     },
        #     "top_informants": informant_stats
        # })
