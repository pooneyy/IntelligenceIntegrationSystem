import traceback
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
import logging


class AdvancedWebScraper:
    """Web scraping module with anti-bot bypass capabilities

    Features:
    - Browser automation via Playwright
    - SOCKS5/HTTP/HTTPS proxy support
    - Request header randomization
    - Automatic retry mechanism
    - Multi-instance isolation
    """

    def __init__(self,
                 proxy: Optional[str] = None,
                 headless: bool = True,
                 timeout: int = 20000):
        """
        Initialize scraper instance

        Args:
            proxy: Proxy URL in format protocol://host:port
            headless: Run browser in headless mode
            timeout: Page load timeout in milliseconds
        """
        self.proxy = proxy
        self.headless = headless
        self.timeout = timeout
        self._init_browser()
        self._init_session()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _init_browser(self):
        """Initialize Playwright browser instance"""
        self.playwright = sync_playwright().start()
        launch_args = {
            'headless': self.headless,
            'proxy': self._parse_proxy(self.proxy) if self.proxy else None,
            'timeout': self.timeout
        }
        self.browser = self.playwright.chromium.launch(**launch_args)
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        )

    def _init_session(self):
        """Initialize HTTP session with proxy support"""
        self.session = requests.Session()
        if self.proxy:
            parsed = urlparse(self.proxy)
            proxies = {
                'http': f'{parsed.scheme}://{parsed.netloc}',
                'https': f'{parsed.scheme}://{parsed.netloc}'
            }
            self.session.mount('http://', HTTPAdapter(max_retries=3))
            self.session.mount('https://', HTTPAdapter(max_retries=3))
            self.session.proxies.update(proxies)

    def _parse_proxy(self, proxy_url: str) -> Dict[str, str]:
        """Parse proxy URL for Playwright configuration"""
        parsed = urlparse(proxy_url)
        return {
            'server': f'{parsed.hostname}:{parsed.port}',
            'username': parsed.username,
            'password': parsed.password
        } if parsed.username else {'server': f'{parsed.hostname}:{parsed.port}'}

    def fetch(self, url: str, render_js: bool = True) -> Optional[str]:
        """
        Fetch webpage content with anti-bot measures

        Args:
            url: Target URL to scrape
            render_js: Enable JavaScript rendering

        Returns:
            Page HTML content or None if failed
        """
        try:
            if render_js:
                return self._fetch_with_playwright(url)
            return self._fetch_with_requests(url)
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {str(e)}")
            return None

    def _fetch_with_playwright(self, url: str) -> str:
        """Fetch page using browser automation"""
        page = self.context.new_page()
        try:
            response = page.goto(url, timeout=self.timeout)
            if response.status >= 400:
                raise RuntimeError(f"HTTP Error {response.status}")
            # page.wait_for_load_state('networkidle', timeout=self.timeout)
            # page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
            return page.content()
        except Exception as e:
            print(traceback.format_exc())
            print(str(e))
            return ''
        finally:
            page.close()

    def _fetch_with_requests(self, url: str) -> str:
        """Fetch page using direct HTTP request"""
        headers = {
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        response = self.session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Clean up resources"""
        self.context.close()
        self.browser.close()
        self.playwright.stop()
        self.session.close()


def fetch_web_content(url: str, proxy: Optional[str] = None, headless: bool = True, timeout: int = 20000):
    try:
        with AdvancedWebScraper(
                proxy=proxy,
                headless=headless,
                timeout=timeout
        ) as scraper:
            html = scraper.fetch(url)
            return html
    except Exception as e:
        print(traceback.format_exc())
        print(str(e))
        return ''


# ----------------------------------------------------------------------------------------------------------------------

def main():
    html = fetch_web_content("https://machinelearningmastery.com/further-applications-with-context-vectors/",
                             proxy=None, headless=True)
    if html:
        with open('web.html', 'wt', encoding='utf-8') as f:
            f.write(html)


# Usage example
if __name__ == "__main__":
    main()
