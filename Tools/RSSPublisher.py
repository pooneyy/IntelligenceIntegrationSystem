import datetime
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
        self.max_items = max_items
        self.feed_items = deque(maxlen=max_items)

        # Load initial items if provided
        if initial_items:
            for item in initial_items:
                self.add_item(**item)

    def add_item(self, title: str, link: str, description: str, pubDate: Optional[datetime.datetime] = None) -> None:
        """
        Add new item to RSS feed

        Args:
            title: Item title
            link: Item URL
            description: Item content summary
            pubDate: Publication datetime (default: current time)
        """
        if not pubDate:
            pubDate = datetime.datetime.now()

        # Create and add new item
        new_item = {
            "title": title,
            "link": link,
            "description": description,
            "pubDate": pubDate
        }
        self.feed_items.append(new_item)

    def generate_feed(self, feed_title: str, feed_link: str, feed_description: str) -> str:
        """
        Generate RSS XML content

        Args:
            feed_title: Channel title
            feed_link: Channel URL
            feed_description: Channel description

        Returns:
            RSS XML string
        """
        rss_items = [
            PyRSS2Gen.RSSItem(
                title=item["title"],
                link=item["link"],
                description=item["description"],
                pubDate=item["pubDate"]
            ) for item in self.feed_items
        ]

        rss = PyRSS2Gen.RSS2(
            title=feed_title,
            link=feed_link,
            description=feed_description,
            lastBuildDate=datetime.datetime.now(),
            items=rss_items
        )

        return rss.to_xml(encoding="utf-8")

    def clear_feed(self) -> None:
        """Clear all feed items"""
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
