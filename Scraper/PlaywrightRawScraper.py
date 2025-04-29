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


def _fetch_content_by_browser(
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
        response = page.goto(url, timeout=timeout, wait_until="load")
        if not response or response.status >= 400:
            raise ValueError(f"HTTP {response.status if response else 'N/A'}")
        raw_content = response.text()
        return raw_content
    except Exception as e:
        return ''
    finally:
        context.close()


def fetch_content(
    url: str,
    timeout_ms: int,
    proxy: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Main entry point for fetching and parsing feeds

    Args:
        url: Feed URL
        proxy: Proxy configuration

    Returns:
        Result dictionary with status details
    """
    try:
        with BrowserManager(headless=True, proxy=proxy) as browser:
            content = _fetch_content_by_browser(url, browser, proxy=proxy)
            return {'content': content, "errors": ''}
    except Exception as e:
        traceback.print_exc()
        return {'content': '', "errors": [str(e)]}


# ----------------------------------------------------------------------------------------------------------------------

def main():
    # SOCKS5 Proxy Example
    proxy_config = {
        "server": "socks5://127.0.0.1:10808",
        "username": "",
        "password": ""
    }

    result = fetch_content(
        "https://blogs.technet.microsoft.com/machinelearning/feed",
        proxy=None
    )

    print(result['content'])
    print(result['errors'])

if __name__ == "__main__":
    main()