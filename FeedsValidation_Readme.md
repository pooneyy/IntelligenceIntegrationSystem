# Feed 验证工具

一个多接口的 RSS/Atom Feed 验证工具，支持本地 API、Web API、命令行和图形界面操作，提供代理支持和多语言友好输出。

## 功能特性

- **四维操作界面**：
  - 🖥️ 图形界面 (PyQt5)
  - ⌨️ 命令行接口
  - 🌐 Web API 服务
  - 📚 本地 Python API

- **核心能力**：
  - 同步/异步验证 Feed 有效性
  - 实时状态追踪 (有效/无效/代理错误/验证中)
  - 代理服务器支持 (HTTP/SOCKS)
  - 跨平台兼容 (Windows/Linux/macOS)

- **数据管理**：
  - 状态记忆存储
  - 智能过滤 (全选/反选/有效项筛选)
  - JSON 格式导入导出
  - 一键清除历史记录

## 安装指南

### 环境要求
- Python ≥ 3.7
- 基础依赖：`pip install requests`

### 可选组件
```bash
# Web 服务支持
pip install flask

# 图形界面支持
pip install pyqt5

# SOCKS 代理支持
pip install requests[socks]
```

## 使用手册

### 1️⃣ 命令行模式
```bash
# 基本验证
python feed_validator.py https://example.com/feed.xml

# 使用代理验证
python feed_validator.py https://internal.site/feed --proxy http://proxy.corp.com:8080

# 启动 Web 服务
python feed_validator.py --web
```

### 2️⃣ Web API 服务
**启动服务**：
```bash
python feed_validator.py --web
```

**API 端点**：
```http
POST /submit
Content-Type: application/json

{
  "proxy": "http://proxy:port",
  "feeds": {
    "新闻频道": "https://news.site/rss",
    "技术博客": "https://tech.blog/atom"
  }
}

GET /status
-> {"https://news.site/rss": "valid", ...}
```

### 3️⃣ 图形界面操作
![GUI 界面截图](gui-screenshot.png)

1. 左侧输入框支持：
   - 直接粘贴 URL
   - 拖放 JSON 文件
   - 手动输入代理设置

2. 右侧功能：
   - 实时状态颜色标记
   - 批量选择操作
   - 动态 JSON 生成
   - 右键菜单管理

### 4️⃣ 本地 Python API
```python
from feed_validator import FeedValidator

# 初始化验证器
validator = FeedValidator(proxies={'https': 'socks5://localhost:9050'})

# 同步验证单个 Feed
is_valid = validator.validate_sync('https://darkweb.site/feed')

# 批量异步验证
validator.add_feeds({"匿名论坛": "https://anon.board/rss"})
validator.validate_async()
```

## 数据格式规范

### 输入 JSON 格式
```json
{
  "proxy": "可选代理地址",
  "feeds": {
    "显示名称": "feed地址",
    "技术新闻": "https://tech.times/feed.xml"
  }
}
```

### 状态说明
| 状态码     | 含义               |
|------------|--------------------|
| valid      | 有效 XML Feed      |
| invalid    | 无效或无法访问     |
| busy       | 验证进行中         |
| proxy_error| 代理连接失败       |

## 高级配置

### 代理服务器支持
支持以下代理类型：
- HTTP 代理：`http://user:pass@host:port`
- HTTPS 代理：`https://proxy.example.com:443`
- SOCKS5 代理：`socks5://127.0.0.1:9050`

### 性能调优
在 `FeedValidator` 初始化时配置：
```python
validator = FeedValidator(
    max_workers=5,      # 并发线程数
    timeout=15,         # 超时时间(秒)
    retry_times=3       # 失败重试次数
)
```

## 常见问题

### Q1: 中文显示乱码
✅ 解决方案：确保系统区域设置为 UTF-8，GUI 界面自动支持中文显示

### Q2: 企业代理验证失败
✅ 排查步骤：
1. 检查代理地址格式是否正确
2. 尝试在命令行使用 `curl -x [proxy] [url]` 测试
3. 验证工具支持 NTLM/Kerberos 认证

### Q3: Web 服务安全问题
🔒 建议方案：
- 添加认证中间件
- 启用 HTTPS
- 限制访问 IP

## 授权许可
本项目采用 [MIT 许可证](LICENSE)，允许自由使用和修改，但需保留版权声明。