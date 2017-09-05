# -*- coding: utf-8 -*-
import scrapy
import sys
import re
import pprint
from unidecode import unidecode
from datetime import datetime
from immo.items import ProductItem
import logging
from pushbullet import Pushbullet
from immo.product import Product, db_connect
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func


class SelogerSpider(scrapy.Spider):
	name = "seloger"
	cat = "ventes_immobilieres"
	origin = "seloger"
	base_url = "http://www.seloger.com/list.htm?idtt=2&idtypebien=2,1,9,14,13&cp=38&tri=initial&naturebien=1,2,4&LISTING-LISTpg="
	pushbullet_api_key = "o.d2sZqMiZoFDv4R2ZkER1wkc6kLdVDRsM"
		
	def __init__(self, *args, **kwargs):
		# disable unuseful logs
		logging.getLogger('scrapy.middleware').setLevel(logging.WARNING)
		logging.getLogger('scrapy.utils.log').setLevel(logging.WARNING)
		logging.getLogger('scrapy.core.engine').setLevel(logging.WARNING)
		logging.getLogger('scrapy.extensions.logstats').setLevel(logging.WARNING)
		logging.getLogger('scrapy.statscollectors').setLevel(logging.WARNING)
		
		super(SelogerSpider, self).__init__(*args, **kwargs)
		
	def start_requests(self):
		# stats init
		self.crawler.stats.set_value('products_created', 0)
		self.crawler.stats.set_value('products_updated', 0)
		self.crawler.stats.set_value('products_failed', 0)
		
		urls = [self.base_url + str(x) for x in range(int(self.start), int(self.end))]	
		for url in urls:
			yield scrapy.Request(url=url, callback=self.parse)

	def parse(self, response):
	
		for elt in response.xpath('//*[@class="content_result"]/section/article[contains(@class, "listing")]'):
	
			the_href = elt.xpath('div/div[contains(@class, "listing_infos")]/h2/a/@href').extract_first()
			
			product = {
				'the_href': the_href,
                'the_title': elt.xpath('div/div[contains(@class, "listing_infos")]/h2/a/text()').extract_first(),
                'the_city': elt.xpath('div/div[contains(@class, "listing_infos")]/h2/a/span/text()').extract_first()
			}
			
			yield scrapy.Request(response.urljoin(the_href), callback=self.parse_product, meta=product, encoding='utf-8')
										
			

	def parse_product(self, response):			
				
		if re.match(".*maison.*", response.meta['the_title'], re.IGNORECASE):
			the_type = "Maison"
		elif re.match(".*appartement.*", response.meta['the_title'], re.IGNORECASE):
			the_type = "Appartement"
		elif re.match(".*terrain.*", response.meta['the_title'], re.IGNORECASE):
			the_type = "Terrain"
		else:
			the_type = "Autre"
			
		the_price = response.xpath('//*[@id="price"]/text()').extract_first()
		the_desc = response.xpath('//p[@class="description"]/text()').extract_first()

		the_surface = the_rooms = None
		for elt in response.xpath('//li[contains(@class, "resume__critere")]'):
			data =  unidecode(elt.xpath('text()').extract_first())
			if re.match(".*pieces.*", data, re.IGNORECASE):
				the_rooms = re.sub('\D', "", data)
			elif re.match(".*m2.*", data, re.IGNORECASE):
				the_surface = re.sub('\sm2', "", data)
		
		the_ref = response.xpath('//span[@class="description_ref"]/text()').extract_first()
		
		product = ProductItem(
			name = response.meta['the_title'][:-2].encode('utf-8'),
			category = self.cat,
			cp = None,
			city = response.meta['the_city'].encode('utf-8'),
			href = response.meta['the_href'].encode('utf-8'),
			img = response.xpath('//img[contains(@class, "carrousel_image_visu")]/@src').extract_first(),
			ref = re.sub("\D", "", the_ref.strip()) if the_ref else None,
			published_at = None,
			price = re.sub("\D", "", the_price.strip()) if the_price else None,
			desc = the_desc.strip().encode('utf-8') if the_desc else None,
			origin = self.origin.encode('utf-8'),
			created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			surface = the_surface.strip() if the_surface else None,
			rooms = the_rooms.strip() if the_rooms else None,
			type = the_type.encode('utf-8'),
			version = 1
		)
		
		if product['desc'] is None:
			print product
		yield(product)
		
	def closed(self, reason):
		self.logger.info("Status: {0}. Stats below".format(reason))
		
		#counting all products
		engine = db_connect()
		Session = sessionmaker(bind=engine)
		session = Session()
		res = session.query(func.count(Product.id))
		count = session.execute(res).first()
		total_count = count[0] if count is not None else 0
		
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(self.crawler.stats.get_stats())
		# send notif
		stats = "{0} CREATED | {1} UPDATED | {2} FAILED | {3} TOTAL".format(self.crawler.stats.get_value('products_created'), self.crawler.stats.get_value('products_updated'), self.crawler.stats.get_value('products_failed'), total_count)
		pb = Pushbullet(self.pushbullet_api_key)
		pb.get_device('Samsung SM-A310F').push_note('Stats {0}'.format(self.name), stats)
		self.logger.info("TOTAL: {0} PRODUCTS".format(total_count))
		
