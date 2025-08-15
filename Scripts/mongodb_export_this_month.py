import datetime
from mongodb_exporter import export_mongodb_data


def get_current_month_range() -> (str, str):
    """获取当前月的起始和结束时间（ISO格式）[1,7](@ref)"""
    today = datetime.datetime.utcnow()
    first_day = datetime.datetime(today.year, today.month, 1)
    last_day = first_day + datetime.timedelta(days=32)
    last_day = datetime.datetime(last_day.year, last_day.month, 1) - datetime.timedelta(seconds=1)
    return first_day.isoformat() + "Z", last_day.isoformat() + "Z"


if __name__ == "__main__":
    # 生成带时间戳的文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    output_file = f"intelligence_archived_month_{timestamp}.json"

    # 获取本月时间范围（ISO格式）[1,6](@ref)
    start_date, end_date = get_current_month_range()

    # 构建本月查询条件
    date_query = {
        "PUB_TIME": {
            "$gte": {"$date": start_date},
            "$lte": {"$date": end_date}
        }
    }

    # 导出 generic_db 数据库中的 intelligence_archived 集合本月记录
    export_mongodb_data(
        uri="mongodb://localhost:27017",  # 根据实际情况修改
        db="generic_db",
        collection="intelligence_archived",
        output_file=output_file,
        query=date_query,
        export_format="json"
    )
