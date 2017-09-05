# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class ProductItem(scrapy.Item):
	name = scrapy.Field()
	category = scrapy.Field()
	cp = scrapy.Field()
	city = scrapy.Field()
	href = scrapy.Field()
	img = scrapy.Field()
	ref = scrapy.Field()
	published_at = scrapy.Field()
	price = scrapy.Field()
	desc = scrapy.Field()
	origin = scrapy.Field()
	created_at = scrapy.Field()
	surface = scrapy.Field()
	rooms = scrapy.Field()
	type = scrapy.Field()
	version = scrapy.Field()
	lon = scrapy.Field()
	lat = scrapy.Field()
	alert_sent = scrapy.Field()
