## IntelligenceIntegrationSystem

情报整合系统：通过抓取主流新闻网站的公开新闻，并使用AI进行分析和评分的情报系统。属于ONIST和一种。

项目地址：[https://github.com/SleepySoft/IntelligenceIntegrationSystem](https://github.com/SleepySoft/IntelligenceIntegrationSystem/tree/dev)

## 起因

现在的新闻素质堪忧，特别是国内媒体。

+ 一方面现代社会每日产生的新闻数量巨大，并且参杂着毫无情报价值的水文。

+ 另一方面媒体看重点击量，所以标题通常无法概括事件。

我一直认为，公开信息中有四成只需要看标题，有两成看总结即可，而只有不到一成的信息有阅读全文的必要。而剩下的三成都是垃圾。

既然媒体们自己不体面，那么我来让新闻体面。

## 原理

本程序核流程为：抓取 -> 提交到情报中心 -> 清洗、AI分析 -> 筛选并重发布 -> 归档

#### 抓取

> 本程序只通过RSS抓取公开新闻，原因在于这类新闻抓取难度小（本身就是给RSS阅读器的公开信息），且法律风险低。

程序中由[ServiceEngine.py](ServiceEngine.py)**启动**并驱动[CrawlTasks](CrawlTasks)目录下的抓取模块，
该服务框架会监控该目录下的文件更新并重新加载更新后的模块。

当前各个抓取模块主要通过[CommonFeedsCrawFlow.py](Workflow/CommonFeedsCrawFlow.py)这个通用流程进行抓取并将抓取内容提交到IntelligenceHub。
抓取模块通过partial构建偏函数供抓取流程调用。

当前实现的抓取方式有：

+ [RequestsScraper.py](Scraper/RequestsScraper.py)：用以抓取简单的内容。最快，但对于动态网页来说抓取不到。
+ [PlaywrightRawScraper.py](Scraper/PlaywrightRawScraper.py)：使用Playwright的无头浏览器抓取 ，速度一般，能抓取到一些requests抓取不到的网页。
+ [PlaywrightRenderedScraper.py](Scraper/PlaywrightRenderedScraper.py)：同是无头浏览器方案，但等待网页渲染完成，最慢，但成功率最高。
+ [Crawl4AI.py](Scraper/Crawl4AI.py)：未实现。

#### IntelligenceHub

+ [IntelligenceHub.py](IntelligenceHub.py)（IHub）：程序的核心。所有的信息都由该组件收集、处理和归档，同时该组件还提供查询服务。
+ [IntelligenceHubWebService.py](IntelligenceHubWebService.py)：为IHub提供网络服务，包括API、网页发布和鉴权。
+ [IntelligenceHubLauncher.py](IntelligenceHubLauncher.py)：IHub的**启动**器，包括初始化所有子组件。



#### 发布


## 环境配置及部署运行

```
# Suggest python 3.10
python -m venv .venv

# Install dependency
pip install -r requirements.txt

# If has dependency issue when using upper command
pip install -r requirements_freeze.txt

# After pip install. Install playwright's headless browser
playwright install chromium

# Switch to venv
.venv/Scripts/activate.bat

# Run main service
python IntelligenceHubLauncher.py

# Run collectors
python ServiceEngine.py
```


https://www.mongodb.com/try/download/database-tools


