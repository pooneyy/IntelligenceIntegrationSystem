from flask import Flask, request, Response, jsonify
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import uuid
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['FEED_TITLE'] = os.getenv('FEED_TITLE', 'My Custom RSS Feed')
app.config['FEED_DESCRIPTION'] = os.getenv('FEED_DESCRIPTION', 'Generated RSS feed from user submissions')
app.config['FEED_LINK'] = os.getenv('FEED_LINK', 'http://localhost:5000')
app.config['PORT'] = int(os.getenv('PORT', 5000))
app.config['API_KEY'] = generate_password_hash(os.getenv('API_KEY', 'default-secret-key'))
app.config['MAX_ITEMS'] = int(os.getenv('MAX_ITEMS', 100))

# 在内存中存储RSS条目
rss_items = []


class RSSItem:
    def __init__(self, title, link, description, author=None, category=None):
        self.id = str(uuid.uuid4())
        self.title = title
        self.link = link
        self.description = description
        self.author = author
        self.category = category
        self.pub_date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def to_rss_element(self):
        item = ET.Element('item')

        title_elem = ET.SubElement(item, 'title')
        title_elem.text = self.title

        link_elem = ET.SubElement(item, 'link')
        link_elem.text = self.link

        desc_elem = ET.SubElement(item, 'description')
        desc_elem.text = self.description

        guid_elem = ET.SubElement(item, 'guid', isPermaLink="false")
        guid_elem.text = self.id

        pub_date_elem = ET.SubElement(item, 'pubDate')
        pub_date_elem.text = self.pub_date

        if self.author:
            author_elem = ET.SubElement(item, 'author')
            author_elem.text = self.author

        if self.category:
            category_elem = ET.SubElement(item, 'category')
            category_elem.text = self.category

        return item


@app.route('/api/add', methods=['POST'])
def add_item():
    # 验证API密钥
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        return jsonify({'error': 'Missing authentication'}), 401

    token = auth[7:]
    if not check_password_hash(app.config['API_KEY'], token):
        return jsonify({'error': 'Invalid API key'}), 401

    # 获取JSON数据
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400

    # 验证必需字段
    if not data.get('title') or not data.get('link') or not data.get('description'):
        return jsonify({'error': 'Missing required fields'}), 400

    # 创建新条目
    try:
        item = RSSItem(
            title=data['title'],
            link=data['link'],
            description=data['description'],
            author=data.get('author'),
            category=data.get('category')
        )
        # 添加到内存存储（限制最大数量）
        rss_items.insert(0, item)
        if len(rss_items) > app.config['MAX_ITEMS']:
            rss_items.pop()

        return jsonify({'message': 'Item added', 'id': item.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/rss')
def rss_feed():
    # 创建RSS根元素
    rss = ET.Element('rss', version="2.0")

    # 创建频道
    channel = ET.SubElement(rss, 'channel')

    # 添加频道元数据
    title = ET.SubElement(channel, 'title')
    title.text = app.config['FEED_TITLE']

    link = ET.SubElement(channel, 'link')
    link.text = app.config['FEED_LINK']

    description = ET.SubElement(channel, 'description')
    description.text = app.config['FEED_DESCRIPTION']

    last_build_date = ET.SubElement(channel, 'lastBuildDate')
    last_build_date.text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    # 添加所有条目
    for item in rss_items[:app.config['MAX_ITEMS']]:
        channel.append(item.to_rss_element())

    # 生成XML响应
    xml = ET.tostring(rss, encoding='utf-8', method='xml')
    return Response(xml, mimetype='application/rss+xml')


def cleanup_old_items():
    """定期清理旧条目（保留30天）"""
    global rss_items
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)

    # 转换日期字符串为时间对象进行比较
    rss_items = [
        item for item in rss_items
        if datetime.strptime(item.pub_date, '%a, %d %b %Y %H:%M:%S GMT') > cutoff
    ]


if __name__ == '__main__':
    # 设置定时任务清理旧条目
    scheduler = APScheduler()
    scheduler.api_enabled = True
    scheduler.init_app(app)
    scheduler.add_job(id='cleanup', func=cleanup_old_items, trigger='interval', hours=12)
    scheduler.start()

    app.run(host='0.0.0.0', port=app.config['PORT'])
