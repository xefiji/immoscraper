# -*- coding: utf-8 -*-

# Scrapy settings for immo project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'immo'

SPIDER_MODULES = ['immo.spiders']

NEWSPIDER_MODULE = 'immo.spiders'

ITEM_PIPELINES = {
    'immo.pipelines.ProductPipeline': 300,
}

MAIL_FROM = "xefiji@fxechappe.fr"

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'immo (+http://www.yourdomain.com)'

LOG_LEVEL = "INFO"

DATABASE = {
    'drivername': 'mysql',
    'host': 'localhost',
    'username': 'xefiji',
    'password': 'glopglop',
    'database': 'labonafer',
    'charset': 'utf8',
}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"

COOKIES_ENABLED = False

# SCRAPOXY SETTINGS (Avoid blacklisting)
# scrapoxy start conf.json -d
# DigitalOcean key:
# 99e2e886af6f4f26a7ab0fa28ab3e5988cc34c7277013303172924573c0cd6f6

CONCURRENT_REQUESTS_PER_DOMAIN = 1

RETRY_TIMES = 0

# PROXY
PROXY = 'http://127.0.0.1:8888/?noconnect'

#WAIT_FOR_SCALE = 30

# SCRAPOXY
API_SCRAPOXY = 'http://127.0.0.1:8889/api'

API_SCRAPOXY_PASSWORD = 'glopglop'

DOWNLOADER_MIDDLEWARES = {
'scrapoxy.downloadmiddlewares.proxy.ProxyMiddleware': 100,
'scrapoxy.downloadmiddlewares.wait.WaitMiddleware': 101,
'scrapoxy.downloadmiddlewares.scale.ScaleMiddleware': 102,
'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': None,
}
