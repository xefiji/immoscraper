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
from sqlalchemy import func, and_
from scrapy.mail import MailSender
from scrapy.exceptions import CloseSpider


class SelogerSpider(scrapy.Spider):
    name = "seloger"
    cat = "ventes_immobilieres"
    origin = "seloger"
    base_url = "http://www.seloger.com/list.htm?cp=38&idtt=2&idtypebien=1,2&naturebien=1,2,4&pxmax=300000&tri=initial&LISTING-LISTpg="
    pushbullet_api_key = "o.d2sZqMiZoFDv4R2ZkER1wkc6kLdVDRsM"
    engine = db_connect()

    def __init__(self, *args, **kwargs):
        # disable unuseful logs
        logging.getLogger('scrapy.middleware').setLevel(logging.WARNING)
        logging.getLogger('scrapy.utils.log').setLevel(logging.WARNING)
        logging.getLogger('scrapy.core.engine').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.logstats').setLevel(logging.WARNING)
        logging.getLogger('scrapy.statscollectors').setLevel(logging.WARNING)

        super(SelogerSpider, self).__init__(*args, **kwargs)

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
        print(response)
        for href in response.xpath('//a[@class="c-pa-link"]'):
            the_href = href.xpath('@href').extract_first()
            product = {
                'the_href': the_href
            }
            yield scrapy.Request(response.urljoin(the_href), callback=self.parse_product, meta=product,
                                 encoding='utf-8')

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
            the_city = elt.xpath('//input[@name="nomville"]/@value').extract_first()
            the_cp = elt.xpath('//input[@name="codepostal"]/@value').extract_first()
            return {'city': the_city, 'cp': the_cp}

        the_title = response.xpath('//h1[contains(@class, "detail-title")]/text()').extract_first()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        the_date = now
        the_hour = now[-8:]
        the_geoloc = get_geoloc(response)
        the_type = "Maison"
        the_surface = response.xpath('//input[@name="surface"]/@value').extract_first()
        the_desc = response.xpath('//p[@id="js-descriptifBien"]/text()').extract_first()
        the_rooms = None
        the_img = response.xpath('//img[contains(@class,"carrousel_image_visu ")]/@src').extract_first()
        the_price = response.xpath('//a[@id="price"]/text()').extract_first()
        try:
            the_price = the_price.replace('\xa0', ' ').replace('\u20ac', ' ').replace(' ', '').strip()
        except:
            pass

        product = ProductItem(
            name=the_title.strip().encode('utf-8') if the_title else None,
            category=self.cat,
            cp=the_geoloc['cp'],
            city=the_geoloc['city'],
            href=response.meta['the_href'].encode('utf-8'),
            img=the_img.encode('utf-8') if the_img else None,
            ref=get_product_id(response.meta['the_href']),
            published_at="{0} {1}:00".format(the_date, the_hour),
            price=the_price.strip() if the_price else None,
            desc=the_desc.strip().encode('utf-8') if the_desc else None,
            origin=self.origin.encode('utf-8'),
            created_at=the_date,
            surface=the_surface.strip() if the_surface else None,
            rooms=the_rooms.strip() if the_rooms else None,
            type=the_type.strip().encode('utf-8') if the_type else None,
            version=1,
            alert_sent=0
        )

        # print(product)
        # raise CloseSpider('Exiting')
        yield (product)

    def closed(self, reason):
        self.logger.info("Status: {0}. Stats below".format(reason))

        # counting all products
        Session = sessionmaker(bind=self.engine)
        session = Session()
        res = session.query(func.count(Product.id)).filter(Product.category == self.cat)
        count = session.execute(res).first()
        total_count = count[0] if count is not None else 0

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.crawler.stats.get_stats())

        # send notif
        stats = "{0} CREATED | {1} UPDATED | {2} FAILED | {3} TOTAL".format(
            self.crawler.stats.get_value('products_created'), self.crawler.stats.get_value('products_updated'),
            self.crawler.stats.get_value('products_failed'), total_count)
        self.send_notif(stats)
        # send email
        self.send_mail()
        self.logger.info("TOTAL: {0} PRODUCTS".format(total_count))

    def send_notif(self, stats):
        pb = Pushbullet(self.pushbullet_api_key)
        pb.get_device('Samsung SM-A310F').push_note('Stats {0}'.format(self.name), stats)

    def send_mail(self):
        cps = [38120, 38950, 38700, 38330, 38920, 38660, 38570, 38190, 38420, 38410, 38320, 38610, 38560, 3845, 38760,
               38640, 38180, 38170, 38600, 38360, 38250, 38400, 38130, 38240, 38560, 38000, 38800, 38220, 38340]
        Session = sessionmaker(bind=self.engine)
        session = Session()
        query = session.query(Product) \
            .filter(Product.category == self.cat) \
            .filter(Product.alert_sent == "0") \
            .filter(Product.cp.in_(cps)) 
            .filter(Product.type == "Maison") \
            .filter(Product.origin == self.origin) \
            .order_by(Product.published_at.desc())

        # no filter on price coz not sure to get them from JS template
        # .filter(and_(Product.price >= 150000, Product.price <= 350000)) \

        res = query.all()
        if len(res) == 0:
            return False

        mail_body = "<html><h1>Dernieres \"Maisons\" mises en ligne sur se loger</h1><p style='color:#42f4a4'><stronng>En vert les baisses potentielles</strong></p><table border=1><tr><th>Photo</th><th>Nom</th><th>Ville</th><th>Prix</th><th>Date</th></tr>"

        for maison in res:
            maison_data = maison.__dict__
            maison_row = "<tr style='background-color: #42f4a4'>" if maison_data['version'] != '1' else "<tr>"
            img = "<img width='250' alt='image' src='" + maison_data['img'] + "'/>" if maison_data[
                                                                                                 'img'] is not None else "-"
            maison_row += "<td>" + img + "</td>"
            name = "<a href='" + (
            maison_data['href'] if maison_data['href'] is not None else "#") + "'>" + unidecode(
                maison_data['name']) + "</a>" if maison_data['name'] is not None else "-"
            maison_row += "<td>" + name + "</td>"
            maison_row += "<td>" + "<strong>{0} {1}</strong>".format(
                unidecode(maison_data['city']) if maison_data['city'] is not None else "-",
                maison_data['cp'] if maison_data['cp'] is not None else "-") + "</td>"
            maison_row += "<td>" + "<strong>" + str(maison_data['price']) + "</strong>" if maison_data[
                                                                                               'price'] is not None else "-" + "</td>"
            maison_row += "<td>" + str(maison_data['published_at']) if maison_data[
                                                                           'published_at'] is not None else "-" + "</td>"
            maison_row += "</tr>"
            mail_body += maison_row
            maison.alert_sent = 1

        session.commit()

        mail_body += "</table></html>"
        mailer = MailSender.from_settings(self.settings)
        subject = "[{0}] Nouvelles maisons en ligne :)".format(self.origin.upper())
        mailer.send(to=["anais.rossettom@gmail.com"], subject=subject, body=mail_body,
                    cc=["fxechappe@gmail.com"], mimetype='text/html')
        # mailer.send(to=["fxechappe@yahoo.fr"], subject="Nouvelles maisons en ligne :)", body=mail_body, cc=["fxechappe@gmail.com"], mimetype='text/html')
        self.logger.info("MAIL has been sent for {0} maisons".format(len(res)))
