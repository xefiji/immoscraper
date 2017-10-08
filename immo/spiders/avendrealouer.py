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


class AvalSpider(scrapy.Spider):
    name = "aval"
    cat = "ventes_immobilieres"
    origin = "avendrealouer"
    domain = "https://www.avendrealouer.fr"
    base_url = "https://www.avendrealouer.fr/recherche.html?sortPropertyName=ReleaseDate&sortDirection=Descending&searchTypeID=1&typeGroupCategoryID=1&transactionId=1&localityIds=3-38&typeGroupIds=1,2,5,9,10,11,12&pageIndex="
    pushbullet_api_key = "o.d2sZqMiZoFDv4R2ZkER1wkc6kLdVDRsM"
    engine = db_connect()

    def __init__(self, *args, **kwargs):
        # disable unuseful logs
        logging.getLogger('scrapy.middleware').setLevel(logging.WARNING)
        logging.getLogger('scrapy.utils.log').setLevel(logging.WARNING)
        logging.getLogger('scrapy.core.engine').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.logstats').setLevel(logging.WARNING)
        logging.getLogger('scrapy.statscollectors').setLevel(logging.WARNING)

        super(AvalSpider, self).__init__(*args, **kwargs)

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
        for href in response.xpath('//*[@id="result-list"]/li[@data-adid]/a'):            
            the_href = href.xpath('@href').extract_first()            
            if re.match(r'.*neuf\.avendrealouer.*', the_href, re.IGNORECASE) is not None:
                continue
            try:    
                url_pos = the_href.index('http')
                the_href = the_href[url_pos:]
            except:
                the_href = self.domain + the_href
            product = {                
                'the_href': the_href
            }
            yield scrapy.Request(response.urljoin(the_href), callback=self.parse_product, meta=product,
                                 encoding='utf-8')

    def parse_product(self, response):

        def get_product_id(elt):
            match = re.search("\d{7,}", elt)
            if match:
                return match.group(0)
            else:
                return None

        def get_geoloc(elt):
            if not elt:
                return None
            try:
                carret_pos = elt.index('<')
                elt = elt[:carret_pos]
            except:
                pass
            the_city = elt[:-7].strip()
            the_cp = elt[-7:].strip().replace(')','').replace('(', '')
            return {'city': the_city, 'cp': the_cp}

        the_title = response.xpath('//meta[@property="og:title"]/@content').extract_first()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        the_date = now
        the_hour = now[-8:]
        the_geoloc = get_geoloc(the_title[the_title.index(', ')+2:])
        the_type = 'Maison'
        try:            
            if the_title and re.match(r'.*maison.*', the_title, re.IGNORECASE) is not None:
                the_type = 'Maison'
            elif (the_title and re.match(r'.*appartement.*', the_title, re.IGNORECASE) is not None):
                the_type = 'Appartement'
        except:
            the_type = 'Maison'
        surface = response.xpath('//span[text()="Surface: "]/following-sibling::span/text()').extract_first()
        the_surface = re.sub('\D', '', surface) if surface else None
        rooms = None
        the_rooms = re.sub('\D', '', rooms) if rooms else None
        the_desc = response.xpath('//div[@id="propertyDesc"]/text()').extract_first()
        the_img = response.xpath('//img[contains(@id, "media")]/@src').extract()
        if len(the_img) > 1 :
            the_img = the_img[1] 
        elif len(the_img) == 1 :
            the_img = the_img[0] 
        else:
            the_img = None

        try:
            the_price = response.xpath('//*[@id="fd-price-val"]/text()').extract_first()
            non_decimal = re.compile(r'[^\d.]+')
            the_price = non_decimal.sub('',unidecode(the_price))
        except:
            the_price = 0

        product = ProductItem(
            name=the_title.strip().encode('utf-8') if the_title else None,
            category=self.cat,
            published_at="{0} {1}:00".format(the_date, the_hour),
            cp=the_geoloc['cp'],
            city=the_geoloc['city'].encode('utf-8'),
            href=response.meta['the_href'].encode('utf-8'),
            img=the_img.encode('utf-8') if the_img else None,
            ref=get_product_id(response.meta['the_href']),
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
            .filter(Product.type == "Maison") \
            .filter(Product.origin == self.origin) \
            .filter(and_(Product.price >= 150000, Product.price <= 350000)) \
            .filter(Product.cp.in_(cps)) \
            .order_by(Product.published_at.desc())

        res = query.all()
        if len(res) == 0:
            return False

        mail_body = "<html><h1>Dernieres \"Maisons\" mises en ligne sur a vendre a louer</h1><p style='color:#42f4a4'><stronng>En vert les baisses potentielles</strong></p><table border=1><tr><th>Photo</th><th>Nom</th><th>Ville</th><th>Prix</th><th>Date</th></tr>"

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
        subject = "{0} - Nouvelles maisons en ligne :)".format(self.origin.upper())
        mailer.send(to=["anais.rossettom@gmail.com"], subject=subject, body=mail_body,
                    cc=["fxechappe@gmail.com"], mimetype='text/html')
        # mailer.send(to=["fxechappe@yahoo.fr"], subject="Nouvelles maisons en ligne :)", body=mail_body, cc=["fxechappe@gmail.com"], mimetype='text/html')
        self.logger.info("MAIL has been sent for {0} maisons".format(len(res)))
