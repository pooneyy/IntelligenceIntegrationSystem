import datetime
import PyRSS2Gen
from typing import List
from pydantic import BaseModel


class FeedItem(BaseModel):
    title: str
    link: str
    description: str | None = None
    pub_date: datetime.datetime | None = None


class RSSPublisher:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def generate_feed(self, channel_title: str, channel_link: str, channel_description: str, feed_items: List[FeedItem]) -> str:
        """
        Generate RSS XML content

        Args:
            channel_title: Channel title
            channel_link: Channel URL
            channel_description: Channel description
            feed_items: Feed items data
        Returns:
            RSS XML string
        """
        rss_items = [
            PyRSS2Gen.RSSItem(
                title=item.title,
                link=self.join_url(self.base_url, item.link),
                description=item.description,
                pubDate=item.pub_date
            ) for item in feed_items
        ]

        rss = PyRSS2Gen.RSS2(
            title=channel_title,
            link=self.join_url(self.base_url, channel_link),
            description=channel_description,
            lastBuildDate=datetime.datetime.now(),
            items=rss_items
        )

        return rss.to_xml(encoding="utf-8")

    @staticmethod
    def join_url(url_prefix: str, link: str):
        return url_prefix.removesuffix('/') + '/' + link.removeprefix('/')