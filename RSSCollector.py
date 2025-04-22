import sqlite3
import pandas as pd
import feedparser


feeds = feedparser.parse('https://example.com/rss')
df = pd.DataFrame([entry for feed in rss_feeds for entry in feeds.entries])



def get_new_entries(feed_url):
    # 连接本地数据库
    conn = sqlite3.connect('rss_history.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS entries (guid TEXT PRIMARY KEY)')

    # 解析 Feed
    feed = feedparser.parse(feed_url)
    new_entries = []

    for entry in feed.entries:
        guid = entry.get('guid', entry.link)  # 回退到 link
        cursor.execute('SELECT 1 FROM entries WHERE guid = ?', (guid,))
        if not cursor.fetchone():
            new_entries.append(entry)
            cursor.execute('INSERT INTO entries (guid) VALUES (?)', (guid,))

    conn.commit()
    conn.close()
    return new_entries

# 使用示例
new_entries = get_new_entries('https://example.com/rss')
print(f"发现 {len(new_entries)} 条新内容")


