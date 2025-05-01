"""
RSS Fetcher with Headless Browser & Proxy Support

Complete implementation with:
- Playwright headless browser
- HTTP/SOCKS5 proxy support
- Random user agents
- Comprehensive error handling
- Type annotations
"""
import re
import random
import traceback

import feedparser
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Browser

import Scraper.RequestsScraper as RequestsScraper

DEFAULT_TIMEOUT_MS = 8000  # 8 seconds
MINIMAL_WAIT_SEC = 2


def parse_feed(content: str) -> dict:
    """
    解析RSS/Atom内容并标准化输出

    :param content: RSS原始内容字符串
    :return: 包含元数据和条目的字典，结构示例：
        {
            "meta": {...},
            "entries": [...],
            "errors": [...]  # 非致命错误集合
        }
    """
    result = {
        "meta": {},
        "entries": [],
        "errors": []
    }

    try:
        # 使用feedparser解析原始内容
        parsed = feedparser.parse(content)

        # 解析状态检测
        if parsed.get("bozo", 0) == 1:
            exc = parsed.get("bozo_exception", Exception("Unknown parsing error"))
            result["errors"].append(f"XML解析错误: {str(exc)}")
            print(f"Feed解析异常: {exc}")

        # 提取元数据
        result["meta"] = {
            "title": parsed.feed.get("title", ""),
            "link": parsed.feed.get("link", ""),
            "description": parsed.feed.get("description", ""),
            "language": parsed.feed.get("language", "unk"),
            "updated": parsed.feed.get("updated_parsed", None)
        }

        # 处理条目
        for entry in parsed.entries:
            processed = {
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "published": entry.get("published_parsed", entry.get("updated_parsed", None)),
                "authors": [a["name"] for a in entry.get("authors", [])],
                "description": sanitize_html(entry.get("description", "")),
                "guid": entry.get("id", ""),
                "categories": entry.get("tags", []),
                "media": extract_media(entry)
            }
            result["entries"].append(processed)

    except Exception as e:
        result["errors"].append(f"致命错误: {str(e)}")
        print(f"解析过程异常: {e}", exc_info=True)

    return result


def sanitize_html(raw: str) -> str:
    """清理HTML标签并保留文本内容"""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


def extract_media(entry) -> list:
    """提取多媒体资源"""
    media = []
    # 处理enclosure标签
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith(("image/", "video/", "audio/")):
            media.append({
                "url": enc["href"],
                "type": enc["type"],
                "length": enc.get("length", 0)
            })
    # 处理media_content扩展
    for mc in entry.get("media_content", []):
        media.append({
            "url": mc["url"],
            "type": mc.get("type", "unknown"),
            "width": mc.get("width", 0),
            "height": mc.get("height", 0)
        })
    return media


def fetch_feed(
    url: str,
    proxy: Optional[Dict[str, str]] = None,
    headless: bool = True
) -> Dict[str, Any]:
    """
    Main entry point for fetching and parsing feeds

    Args:
        url: Feed URL
        proxy: Proxy configuration
        headless: Browser visibility mode

    Returns:
        Result dictionary with status details
    """
    try:
        result = RequestsScraper.fetch_content(url, timeout_ms=DEFAULT_TIMEOUT_MS)
        if result['content']:
            parsed = parse_feed(result['content'])
            return parsed
        else:
            return {
                "url": url,
                "error": "Empty content",
                "status": "Fetch Failed"
            }
    except Exception as e:
        traceback.print_exc()
        return {"url": url, "errors": [str(e)]}


# ----------------------------------------------------------------------------------------------------------------------

def main():
    # SOCKS5 Proxy Example
    proxy_config = {
        "server": "socks5://127.0.0.1:10808",
        "username": "",
        "password": ""
    }

    result = fetch_feed(
        "https://feeds.feedburner.com/zhihu-daily",
        proxy=None
    )

    if 'entries' in result:
        for index, entry in enumerate(result['entries']):
            print(f'Item {index} : ')
            for k in sorted(entry.keys()):
                print(f'    {k} : {entry[k]}')

    # The entry dict looks like:
    # {
    #     'authors':        ['...'],
    #     'categories':     ['...'],
    #     'description':    '...',
    #     'guid':           '...',
    #     'link':           '...',
    #     'media':          { '...': '...' },
    #     'published':      '...',
    #     'title':          '...',
    # }

    if 'errors' in result:
        print(f'Errors: {result["errors"]}')

if __name__ == "__main__":
    main()