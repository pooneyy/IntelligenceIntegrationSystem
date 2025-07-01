import datetime
import threading

import PyRSS2Gen
from collections import deque
from typing import List, Dict, Optional


class RSSPublisher:
    def __init__(self, max_items: int = 100, initial_items: Optional[List[Dict]] = None):
        """
        Initialize RSS publisher with configuration

        Args:
            max_items: Maximum items to maintain in feed
            initial_items: Initial feed items in format:
                [{"title": "X", "link": "url", "description": "...", "pubDate": datetime}, ...]
        """
        self.lock = threading.Lock()
        self.max_items = max_items
        self.feed_items = deque(maxlen=max_items)

        self.rss_cache = ''
        self.rss_revision = 0           # The revision of rss xml
        self.feeds_revision = 0         # The revision of feeds data

        # Load initial items if provided
        if initial_items:
            for item in initial_items:
                self.add_item(**item)

    def add_item(self, title: str, link: str, description: str, pub_data: Optional[datetime.datetime] = None) -> None:
        """
        Add new item to RSS feed

        Args:
            title: Item title
            link: Item URL
            description: Item content summary
            pub_data: Publication datetime (default: current time)
        """
        if not pub_data:
            pub_data = datetime.datetime.now()

        # Create and add new item
        new_item = {
            "title": title,
            "link": link,
            "description": description,
            "pubDate": pub_data
        }

        with self.lock:
            self.feed_items.append(new_item)
            self.feeds_revision += 1

    def generate_feed(self, channel_title: str, channel_link: str, channel_description: str) -> str:
        """
        Generate RSS XML content

        Args:
            channel_title: Channel title
            channel_link: Channel URL
            channel_description: Channel description

        Returns:
            RSS XML string
        """
        with self.lock:
            if self.rss_revision == self.feeds_revision:
                return self.rss_cache

            rss_items = [
                PyRSS2Gen.RSSItem(
                    title=item["title"],
                    link=item["link"],
                    description=item["description"],
                    pubDate=item["pubDate"]
                ) for item in self.feed_items
            ]

            rss = PyRSS2Gen.RSS2(
                title=channel_title,
                link=channel_link,
                description=channel_description,
                lastBuildDate=datetime.datetime.now(),
                items=rss_items
            )

            self.rss_cache = rss.to_xml(encoding="utf-8")

            return self.rss_cache

    def clear_feed(self) -> None:
        """Clear all feed items"""
        with self.lock:
            self.feed_items.clear()


# ----------------------------------------------------------------------------------------------------------------------

def main():
    from flask import Flask, request, Response
    import datetime

    app = Flask(__name__)

    # Initialize publisher with sample data
    INITIAL_ITEMS = [
        {
            "title": "Initial Post",
            "link": "https://example.com/initial",
            "description": "Initial feed item",
            "pubDate": datetime.datetime(2023, 1, 1)
        }
    ]
    publisher = RSSPublisher(max_items=50, initial_items=INITIAL_ITEMS)

    @app.route('/add', methods=['POST'])
    def add_item():
        """Add new item to RSS feed"""
        data = request.json
        publisher.add_item(
            title=data["title"],
            link=data["link"],
            description=data["description"]
        )
        return {"status": "success"}, 201

    @app.route('/rss', methods=['GET'])
    def get_feed():
        """Get current RSS feed"""
        feed_xml = publisher.generate_feed(
            feed_title="Custom RSS Feed",
            feed_link="https://example.com/rss",
            feed_description="Dynamically generated RSS feed"
        )
        return Response(feed_xml, mimetype="application/xml")

    app.run(host="0.0.0.0", port=8080)


if __name__ == '__main__':
    main()
