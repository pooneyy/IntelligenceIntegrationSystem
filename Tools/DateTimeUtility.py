import re
import datetime

def time_str_to_datetime(text: str) -> datetime.datetime or None:
    # 预处理：移除多余空格和时区简写（如CST）
    text = re.sub(r"\s*(?:[A-Z]{3,4})\s*$", "", text.strip())

    # ISO 8601格式（含时区）
    if "T" in text or "+" in text or "-" in text and text.count("-") > 2:
        try:
            return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass

    formats = [
        '%Y-%m-%d %H:%M:%S',  # 标准日期时间
        '%Y-%m-%d',  # 仅日期
        '%Y%m%d',  # 紧凑日期
        '%H:%M:%S',  # 仅时间 → 自动补全为当日
        '%m/%d/%Y %I:%M %p',  # 美式日期+12小时制
        '%d %b %Y',  # "07 Aug 2025"
        '%d %B %Y'  # "07 August 2025"
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(text, fmt)
            # 仅时间处理：补全为当日
            if fmt == '%H:%M:%S':
                now = datetime.datetime.now()
                return dt.replace(year=now.year, month=now.month, day=now.day)
            return dt
        except ValueError:
            continue

    return None
