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

DEFAULT_TIMEOUT_MS = 8000  # 8 seconds
MINIMAL_WAIT_SEC = 2

class ProxyConnectionError(Exception):
    """Custom exception for proxy related errors"""
    pass

# 更新UA列表为完整现代浏览器标识
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


class BrowserManager:
    """Manage browser instance with proxy and anti-detection settings"""

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[Dict[str, str]] = None,
        user_agents: Optional[List[str]] = None
    ):
        self.playwright = sync_playwright().start()
        self.proxy = proxy
        self.user_agents = user_agents or DEFAULT_USER_AGENTS

        launch_options = self._prepare_launch_options(headless)
        self.browser = self.playwright.chromium.launch(**launch_options)

    def _prepare_launch_options(self, headless: bool) -> Dict[str, Any]:
        options = {
            "headless": headless,
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--disable-automation-software-banner',  # 隐藏自动化提示
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-site-isolation-trials',  # 禁用站点隔离
                '--disable-features=IsolateOrigins,site-per-process',
                f'--window-size={random.randint(1000, 1400)},{random.randint(800, 1200)}'  # 随机窗口尺寸
            ],
            "slow_mo": random.uniform(100, 500),  # 模拟人类操作间隔
        }

        if self.proxy:
            self._validate_proxy_config()
            options["proxy"] = {
                "server": self.proxy["server"],
                "username": self.proxy.get("username"),
                "password": self.proxy.get("password")
            }

        return options

    def _validate_proxy_config(self):
        """Validate proxy configuration format"""
        if not re.match(
            r"^(http|https|socks5)://([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+:\d+$",
            self.proxy["server"]
        ):
            raise ValueError(f"Invalid proxy server format: {self.proxy['server']}")

    def __enter__(self) -> Browser:
        return self.browser

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.browser.close()
        self.playwright.stop()

def fetch_feed_content(
        url: str,
        browser: Browser,
        timeout: int = DEFAULT_TIMEOUT_MS,
        proxy: Optional[Dict[str, str]] = None
) -> Optional[str]:
    context_args = {
        "user_agent": random.choice(DEFAULT_USER_AGENTS),
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "java_script_enabled": False,  # 禁用JavaScript
        "ignore_https_errors": True,
        "extra_http_headers": {
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",  # 指定内容类型
        }
    }

    if proxy:
        context_args["proxy"] = {
            "server": proxy["server"],
            "username": proxy.get("username"),
            "password": proxy.get("password")
        }

    context = browser.new_context(**context_args)
    page = context.new_page()

    try:
        # 发起请求并等待到响应完成
        response = page.goto(url, timeout=timeout, wait_until="load")
        if not response or response.status >= 400:
            raise ValueError(f"HTTP {response.status if response else 'N/A'}")

        # 验证内容类型是否为XML
        content_type = response.headers.get('content-type', '').lower()
        if 'xml' not in content_type:
            print(f"Warning: Unexpected content type {content_type} for URL {url}")

        # 获取原始响应文本
        raw_content = response.text()
        return raw_content

    except Exception as e:
        if "timeout" in str(e).lower():
            print(f"Timeout occurred: {url}")
        elif "net::ERR_PROXY_CONNECTION_FAILED" in str(e):
            raise ProxyConnectionError("Proxy connection failed")
        return None
    finally:
        context.close()

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
        with BrowserManager(headless=headless, proxy=proxy) as browser:
            content = fetch_feed_content(url, browser, proxy=proxy)

            if not content:
                return {
                    "status": "fetch_failed",
                    "url": url,
                    "error": "Empty content"
                }

            parsed = parse_feed(content)
            return parsed
    except Exception as e:
        traceback.print_exc()
        return {"errors": [str(e)]}


# ----------------------------------------------------------------------------------------------------------------------

def main():
    # SOCKS5 Proxy Example
    proxy_config = {
        "server": "socks5://127.0.0.1:10808",
        "username": "",
        "password": ""
    }

    result = fetch_feed(
        "https://blogs.technet.microsoft.com/machinelearning/feed",
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