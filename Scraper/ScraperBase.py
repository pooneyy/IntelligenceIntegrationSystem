"""
All scraper MUST provide the same interface and the same result format.
"""
from typing import Optional, Dict, Any


def fetch_content(
    url: str,
    timeout_ms: int,
    proxy: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Fetch web content from the specified url.
    :param url: The url to fetch.
    :param timeout_ms: The timeout in ms.
    :param proxy: The proxy setting. Currently, there are 2 kinds of proxy format. We're going to make them the same.
    :return:
        {
            'content': '',                  # The content in str. If it's an empty string, that means scrap fail.
            'errors': [''],                 # The error list in str
            'other optional fields': Any    # Any other extra fields that depends on scraper itself.
        }
    """
    return {
        'content': '',
        'errors': ['This is just an example of scraper implementation,'],

        'url': url,
        'timeout_ms': timeout_ms,
        'proxy': proxy
    }

