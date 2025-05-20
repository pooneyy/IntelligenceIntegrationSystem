import asyncio
from typing import List, Optional, TypedDict
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, JsonCssExtractionStrategy, CacheMode

from Scraper.ScraperBase import ScraperResult, ProxyConfig


async def _async_fetch(
        url: str,
        timeout_ms: int,
        proxy: Optional[ProxyConfig] = None,
        **kwargs
) -> ScraperResult:
    result = {"content": "", "errors": []}

    browser_config = BrowserConfig(
        user_agent_mode="random",
        user_agent_generator_config={"device_type": "desktop"},
        proxy_config={"server": proxy.get('http', '')},
        viewport={"width": 1280, "height": 720},
    )

    schema = {"selector": "div.article", "fields": [...]}
    run_config = CrawlerRunConfig(
        extraction_strategy=JsonCssExtractionStrategy(schema),
        cache_mode=CacheMode.BYPASS,
    )

    try:
        async with AsyncWebCrawler(browser_config=browser_config) as crawler:
            response = await crawler.arun(
                url=url,
                run_config=run_config
            )

            if response.success:
                result["content"] = response.markdown
            else:
                result["errors"].append(f"STATUS:{response.status_code} | {response.error}")

    except Exception as e:
        error_msg = f"CRITICAL:{str(e)}"
        result["errors"].append(error_msg)

    return result


def fetch_content(**kwargs) -> ScraperResult:
    return asyncio.run(_async_fetch(**kwargs))
