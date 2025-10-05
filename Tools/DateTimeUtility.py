import re
import logging
import datetime
from typing import Union, Optional

import pytz

logger = logging.getLogger(__name__)

# Default format constants
DEFAULT_YEAR_FORMAT = "%Y"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M:%S"
DEFAULT_DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 时区常量
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


def ensure_local_timezone(dt: datetime.datetime) -> datetime.datetime:
    """将datetime对象转换为本地时区(北京时间)"""
    if dt.tzinfo is None:
        # Naive时间视为本地时区
        return LOCAL_TIMEZONE.localize(dt)
    else:
        # Aware时间直接转换到本地时区
        return dt.astimezone(LOCAL_TIMEZONE)


def any_time_to_time_str(dt: Union[datetime.datetime, datetime.date, int, float, str, None],
                         show_time: bool = True) -> str:
    """将多种时间表示转换为本地时区的格式化字符串"""
    if dt is None:
        logger.warning("Received None input, returning empty string")
        return ""

    original_type = type(dt).__name__

    try:
        # 处理datetime对象
        if isinstance(dt, datetime.datetime):
            logger.debug(f"Processing datetime object: {dt}")
            # 确保转换到本地时区再格式化
            dt_local = ensure_local_timezone(dt)
            return dt_local.strftime(DEFAULT_DATE_TIME_FORMAT if show_time else DEFAULT_DATE_FORMAT)

        # 处理date对象（纯日期）
        elif isinstance(dt, datetime.date):
            logger.debug(f"Processing date object: {dt}")
            logger.info("Ignored show_time parameter for date-only object")
            return dt.strftime(DEFAULT_DATE_FORMAT)

        # 处理时间戳（整数/浮点数）
        elif isinstance(dt, (int, float)):
            logger.debug(f"Processing timestamp: {dt}")
            # 时间戳视为UTC时间，再转换到本地时区
            utc_dt = datetime.datetime.utcfromtimestamp(dt).replace(tzinfo=pytz.utc)
            dt_local = ensure_local_timezone(utc_dt)
            return dt_local.strftime(DEFAULT_DATE_TIME_FORMAT if show_time else DEFAULT_DATE_FORMAT)

        # 处理字符串输入
        elif isinstance(dt, str):
            logger.debug(f"Processing string input: {dt}")
            # 时间戳字符串处理
            if re.match(r'^\d+$', dt):
                try:
                    timestamp = int(dt)
                    utc_dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
                    dt_local = ensure_local_timezone(utc_dt)
                    return dt_local.strftime(DEFAULT_DATE_TIME_FORMAT if show_time else DEFAULT_DATE_FORMAT)
                except (ValueError, OSError) as e:
                    logger.warning(f"Timestamp conversion failed: {str(e)}")

            # 非时间戳字符串解析
            parsed = time_str_to_datetime(dt)
            if parsed:
                # 递归处理确保时区转换[7](@ref)
                return any_time_to_time_str(parsed, show_time)
            else:
                logger.warning(f"Failed to parse time string: {dt}")
                return dt

        # 不支持的类型
        else:
            raise TypeError(f"Unsupported type: {original_type}")

    except Exception as e:
        logger.error(f"Conversion failed for {dt} ({original_type}): {str(e)}")
        return str(dt)


def time_str_to_datetime(text: str) -> Optional[datetime.datetime]:
    """解析字符串为datetime对象，保留原始时区信息"""
    text = text.strip()
    if not text:
        logger.warning("Received empty string input")
        return None

    # 1. 处理时间戳字符串
    if re.match(r'^\d+$', text):
        try:
            timestamp = int(text)
            return datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
        except (ValueError, OSError) as e:
            logger.warning(f"Timestamp conversion failed: {str(e)}")

    # 2. 处理ISO格式（含时区）
    if "Z" in text or "+" in text or "T" in text:
        try:
            normalized = text.replace("Z", "+00:00")
            # 解析并保留原始时区[3,4](@ref)
            return datetime.datetime.fromisoformat(normalized)
        except ValueError as e:
            logger.warning(f"ISO format parsing failed: {str(e)}")

    # 3. 尝试常见日期格式（无时区）
    cleaned_text = re.sub(r"\s*(?:[A-Z]{3,4})\s*$", "", text)
    formats = [
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y%m%dT%H%M%S',
        '%Y-%m', '%Y %m', '%Y-%m-%d', '%Y%m%d', '%H:%M:%S', '%m/%d/%Y %I:%M %p',
        '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y',
        '%Y-%m-%d %H:%M', '%m/%d/%Y', '%d.%m.%Y', '%Y年%m月%d日 %H时%M分%S秒'
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(cleaned_text, fmt)
            logger.debug(f"Successfully parsed with format: {fmt}")

            # 纯时间格式添加当前日期[6](@ref)
            if fmt in ['%H:%M:%S', '%H:%M']:
                now = datetime.datetime.now()
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
                logger.info("Time-only input defaulted to current date")

            # 返回naive datetime对象（无时区）
            return dt
        except ValueError:
            continue

    logger.error(f"All parsing attempts failed for: {text}")
    return None


# ----------------------------------------------------------------------------------------------------------------------

def run_tests():
    # 预定义测试时间
    naive_dt = datetime.datetime(2023, 5, 15, 10, 30)  # Naive datetime
    utc_dt = datetime.datetime(2023, 5, 15, 2, 30, tzinfo=pytz.utc)  # UTC时间
    date_obj = datetime.date(2023, 5, 15)  # 纯日期对象
    timestamp = 1684117800  # UTC时间戳（对应2023-05-15 10:30:00 UTC+8）

    # 1. 测试 any_time_to_time_str 函数
    print("===== 测试 any_time_to_time_str =====")

    # 1.1 Naive datetime（无时区）
    result = any_time_to_time_str(naive_dt)
    assert result == "2023-05-15 10:30:00", f"Naive datetime 测试失败: {result}"
    print(f"[✓] Naive datetime: {result}")

    # 1.2 Aware datetime（UTC时区）
    result = any_time_to_time_str(utc_dt)
    assert result == "2023-05-15 10:30:00", f"UTC datetime 测试失败: {result}"
    print(f"[✓] UTC datetime: {result}")

    # 1.3 纯日期对象（忽略show_time）
    result = any_time_to_time_str(date_obj)
    assert result == "2023-05-15", f"Date对象测试失败: {result}"
    print(f"[✓] Date对象: {result}")

    # 1.4 时间戳（整数）
    result = any_time_to_time_str(timestamp)
    assert result == "2023-05-15 10:30:00", f"时间戳(整数)测试失败: {result}"
    print(f"[✓] 时间戳(整数): {result}")

    # 1.5 时间戳（字符串）
    result = any_time_to_time_str("1684117800")
    assert result == "2023-05-15 10:30:00", f"时间戳(字符串)测试失败: {result}"
    print(f"[✓] 时间戳(字符串): {result}")

    # 1.7 跨年时间
    result = any_time_to_time_str("2023-12-31 23:30")
    assert result.startswith("2023-12-31"), f"跨年测试失败: {result}"
    print(f"[✓] 跨年时间: {result}")

    # 1.8 纯时间字符串（自动补全日期）
    result = any_time_to_time_str("10:30:00")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    assert result == f"{today} 10:30:00", f"纯时间测试失败: {result}"
    print(f"[✓] 纯时间字符串: {result}")

    # 1.9 None输入
    result = any_time_to_time_str(None)
    assert result == "", f"None输入测试失败: {result}"
    print(f"[✓] None输入: 返回空字符串")

    # 2. 测试 time_str_to_datetime 函数
    print("\n===== 测试 time_str_to_datetime =====")

    # 2.1 ISO格式（含时区）
    dt = time_str_to_datetime("2023-05-15T02:30:00+00:00")
    assert dt == utc_dt, f"ISO含时区测试失败: {dt}"
    print(f"[✓] ISO含时区: {dt}")

    # 2.2 日期字符串（无时区）
    dt = time_str_to_datetime("2023-05-15")
    assert dt == naive_dt.replace(hour=0, minute=0), f"日期字符串测试失败: {dt}"
    print(f"[✓] 日期字符串: {dt}")

    # 2.3 时间字符串（自动补全日期）
    dt = time_str_to_datetime("10:30:00")
    now = datetime.datetime.now()
    expected = datetime.datetime(now.year, now.month, now.day, 10, 30)
    assert dt == expected, f"纯时间测试失败: {dt}"
    print(f"[✓] 纯时间字符串: {dt}")

    # 2.4 混合格式（中文日期）
    dt = time_str_to_datetime("2023年05月15日 10时30分00秒")
    assert dt == naive_dt, f"中文日期测试失败: {dt}"
    print(f"[✓] 中文日期: {dt}")

    # 2.5 无效格式
    dt = time_str_to_datetime("InvalidTime")
    assert dt is None, f"无效格式测试失败: {dt}"
    print("[✓] 无效格式: 返回None")

    print("\n===== 所有测试通过 =====")


# 执行测试
if __name__ == "__main__":
    # 临时降低日志级别避免干扰
    logging.getLogger().setLevel(logging.ERROR)
    run_tests()
