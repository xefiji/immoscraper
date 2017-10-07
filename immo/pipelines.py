    # -*- coding: utf-8 -*-
import requests
from product import Product, db_connect, create_product_table
from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc, select
import re


# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

# Test comment

class ProductPipeline(object):
    # TODO: what about http://adresse.data.gouv.fr/api/ ???
    mapquest_url = "http://open.mapquestapi.com/nominatim/v1/search.php?key=" + "YSblqC5fOqO8aRkzrFFpiAD2G28gOrP3" + "&limit=1&format=json&q="

    def __init__(self):
        """
        Initializes database connection and sessionmaker.
        Creates deals table.
        """
        engine = db_connect()
        create_product_table(engine)
        self.Session = sessionmaker(bind=engine)

    def process_item(self, item, spider):
        '''
        # should be part of another cronjob:
        lat_lon = self.get_coords({'city': item.get('city'), 'cp': item.get('cp')})
        item['lon'], item['lat'] = lat_lon['lon'], lat_lon['lat']
        '''
        session = self.Session()
        product = Product(**item)

        try:
            session.add(product)
            session.commit()
            spider.crawler.stats.inc_value('products_created')
        except exc.IntegrityError as e:
            session.rollback()
            s = select([Product]).where(Product.ref == item.get('ref')).where(Product.origin == item.get('origin')).order_by(Product.created_at.desc()).limit(1)        
            for row in session.execute(s):
                if row.price is not None and item.get('price') is not None and re.search('[^0-9]', item.get('price')) is None:
                    if int(row.price) != int(item.get('price')):
                        try:
                            item['version'] = int(row.version) + 1
                            product = Product(**item)
                            session.add(product)
                            session.commit()
                            spider.crawler.stats.inc_value('products_updated')
                        except Exception as e:
                            session.rollback()
                            spider.logger.error(e.message)
                            spider.crawler.stats.inc_value('products_failed')
        except Exception as e:
            session.rollback()
            spider.logger.error(e.message)
            spider.crawler.stats.inc_value('products_failed')
        finally:
            session.close()

        return item

    def get_coords(self, the_geoloc):
        if len(the_geoloc["city"]) == 0:
            query = str(the_geoloc["cp"]) + " France"
        elif the_geoloc["cp"] == 0:
            query = the_geoloc["city"] + " France"
        else:
            query = the_geoloc["city"] + " " + str(the_geoloc["cp"]) + " France"

        try:
            data = requests.get(self.mapquest_url + query)
            if data.json() and len(data.json()) == 0:
                return {'lon': '', 'lat': ''}
            else:
                if data.json()[0]:
                    return {'lon': data.json()[0]['lon'], 'lat': data.json()[0]['lat']}
                return {'lon': '', 'lat': ''}
        except Exception as e:
            # print(e)
            return {'lon': 0, 'lat': 0}
