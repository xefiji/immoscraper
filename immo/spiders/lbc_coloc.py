# -*- coding: utf-8 -*-
import scrapy
import sys
import re
import pprint
from datetime import datetime
from unidecode import unidecode
from immo.items import ProductItem
import logging
from pushbullet import Pushbullet
from immo.product import Product, db_connect
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from scrapy.mail import MailSender
from scrapy.exceptions import CloseSpider


class LbcColocSpider(scrapy.Spider):
	name = "lbc_coloc"
	cat = "colocations"
	origin = "leboncoin"
	base_url = "https://www.leboncoin.fr/colocations/offres/rhone_alpes/isere/?q=maison&o="
	pushbullet_api_key = "o.d2sZqMiZoFDv4R2ZkER1wkc6kLdVDRsM"
	engine = db_connect()
		
	def __init__(self, *args, **kwargs):
		# disable unuseful logs
		logging.getLogger('scrapy.middleware').setLevel(logging.WARNING)
		
		logging.getLogger('scrapy.utils.log').setLevel(logging.WARNING)
		logging.getLogger('scrapy.core.engine').setLevel(logging.WARNING)
		logging.getLogger('scrapy.extensions.logstats').setLevel(logging.WARNING)
		logging.getLogger('scrapy.statscollectors').setLevel(logging.WARNING)
		
		super(LbcColocSpider, self).__init__(*args, **kwargs)
		
	def start_requests(self):		
		# raise CloseSpider('Exiting')
		# stats init
		self.crawler.stats.set_value('products_created', 0)
		self.crawler.stats.set_value('products_updated', 0)
		self.crawler.stats.set_value('products_failed', 0)
		
		urls = [self.base_url + str(x) for x in range(int(self.start), int(self.end))]	
		for url in urls:
			yield scrapy.Request(url=url, callback=self.parse)

	def parse(self, response):
		for href in response.xpath('//*[@id="listingAds"]/section/section/ul/li/a'):
			the_href = href.xpath('@href').extract_first()							
			product = {
				'the_title': href.css(u'.item_title::text').extract_first().strip(),
                'the_href': the_href
			}
			yield scrapy.Request(response.urljoin(the_href), callback=self.parse_product, meta=product, encoding='utf-8')

	def parse_product(self, response):

		def get_product_id(elt):
			match = re.search("\d{4,}", elt)
			if match:
				return match.group(0)
			else:
				return None
				
		def get_geoloc(elt):
			if not elt:
				return None
			the_city = elt.strip()[0:-6]
			the_cp = elt.strip()[len(elt.strip()[0:-5]):]
			return {'city': the_city, 'cp': the_cp}
	
		the_date = response.xpath('//*[@itemprop="availabilityStarts"]/@content').extract_first()
		the_hour = response.xpath('//*[@itemprop="availabilityStarts"]/text()').extract_first()[-5:]
		the_geoloc =  get_geoloc(response.xpath('//*[@itemprop="address"]/text()').extract_first())
		the_type = response.xpath('//*[@class="property" and text()="Type de bien"]/following-sibling::span/text()').extract_first()
		surface = response.xpath('//*[@class="property" and text()="Surface"]/following-sibling::span/text()').extract_first()
		the_surface = re.sub('\D', '', surface) if surface else None
		the_desc = " ".join(response.xpath('//*[@itemprop="description"]/text()').extract())
		# the_rooms = response.xpath(u'//*[@class="property" and text()="Pièces"]/following-sibling::span/text()').extract_first()
		the_img = response.xpath('//*[@id="item_image"]/span/@data-imgsrc').extract_first()				
				
		product = ProductItem(
			name = response.meta['the_title'].encode('utf-8'),
			category = self.cat,
			cp = the_geoloc['cp'],
			city = the_geoloc['city'].encode('utf-8'),
			href = response.meta['the_href'].encode('utf-8'),
			img = the_img.encode('utf-8') if the_img else None,
			ref = get_product_id(response.meta['the_href']),
			published_at = "{0} {1}:00".format(the_date, the_hour),
			price = response.xpath('//*[@itemprop="price"]/@content').extract_first(),
			desc = the_desc.strip().encode('utf-8') if the_desc else None,
			origin = self.origin.encode('utf-8'),
			created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			surface = the_surface.strip() if the_surface else None,
			# rooms = the_rooms.strip() if the_rooms else None,
			type = the_type.strip().encode('utf-8') if the_type else None,
			version = 1,
			alert_sent = 0
		)
		
		yield(product)
		
	def closed(self, reason):
		self.logger.info("Status: {0}. Stats below".format(reason))
		
		#counting all products		
		Session = sessionmaker(bind=self.engine)
		session = Session()
		res = session.query(func.count(Product.id)).filter(Product.category==self.cat)
		count = session.execute(res).first()
		total_count = count[0] if count is not None else 0
		
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(self.crawler.stats.get_stats())
		stats = "{0} CREATED | {1} UPDATED | {2} FAILED | {3} TOTAL".format(self.crawler.stats.get_value('products_created'), self.crawler.stats.get_value('products_updated'), self.crawler.stats.get_value('products_failed'), total_count)
		# send notif
		self.send_notif(stats)
		#send email
		self.send_mail()
		self.logger.info("TOTAL: {0} PRODUCTS".format(total_count))
		
		
	def send_notif(self, stats):
		pb = Pushbullet(self.pushbullet_api_key)
		pb.get_device('Samsung SM-A310F').push_note('Stats {0}'.format(self.name), stats)
		
	def send_mail(self):
	
		Session = sessionmaker(bind=self.engine)
		session = Session()
		res = session.query(Product).filter(Product.category==self.cat).filter(Product.alert_sent=="0").order_by(Product.published_at.desc()).all()
		
		if len(res) == 0:
			return False
			
		mail_body = "<html><h1>Dernieres colocs \"Maisons\" mises en ligne sur le bon coin</h1><table border=1><tr><th>Photo</th><th>Nom</th><th>Ville</th><th>Prix</th><th>Date</th></tr>"
					
		for coloc in res:
			coloc_data = coloc.__dict__			
			coloc_row = "<tr>"
			img = "<img width='250' alt='image' src='http:" + coloc_data['img'] + "'/>" if coloc_data['img'] is not None else "-" 
			coloc_row += "<td>" + img + "</td>"
			name = "<a href='http:" + (coloc_data['href'] if coloc_data['href'] is not None else "#") + "'>" + unidecode(coloc_data['name']) + "</a>" if coloc_data['name'] is not None else "-"
			coloc_row += "<td>" + name + "</td>"
			coloc_row += "<td>" + "<strong>{0} {1}</strong>".format(unidecode(coloc_data['city']) if coloc_data['city'] is not None else "-", coloc_data['cp'] if coloc_data['cp'] is not None else "-") + "</td>"
			coloc_row += "<td>" + "<strong>" + str(coloc_data['price']) + "</strong>" if coloc_data['price'] is not None else "-" + "</td>"
			coloc_row += "<td>" + str(coloc_data['published_at']) if coloc_data['published_at'] is not None else "-" + "</td>"
			coloc_row += "</tr>"
			mail_body += coloc_row
			coloc.alert_sent = 1
		
		session.commit()
				
		mail_body += "</table></html>"
		mailer = MailSender.from_settings(self.settings)
		mailer.send(to=["rbu2000@yahoo.fr"], subject="Nouvelles colocs en ligne :)", body=mail_body, cc=["fxechappe@gmail.com"], mimetype='text/html')
		# mailer.send(to=["fxechappe@yahoo.fr"], subject="Nouvelles colocs en ligne :)", body=mail_body, cc=["fxechappe@gmail.com"], mimetype='text/html')
		self.logger.info("MAIL has been sent for {0} colocs".format(len(res)))

