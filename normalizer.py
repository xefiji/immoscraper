# -*- coding: utf-8 -*-
from immo.product import Product, db_connect
from sqlalchemy.orm import sessionmaker
from sqlalchemy import or_
import requests, time, sys


class Normalizer(object):

	active_api = "google" # | mapquest. (todo: what about http://adresse.data.gouv.fr/api/ ?)
	mapquest_apikey = "[KEYHERE]"
	google_apikey = "[KEYHERE]"

	def __init__(self):		
		engine = db_connect()		
		Session = sessionmaker(bind=engine)
		self.session_instance = Session()
		# TODO: what about http://adresse.data.gouv.fr/api/ ???
		self.mapquest_api_url = "http://open.mapquestapi.com/nominatim/v1/search.php?key=" + self.mapquest_apikey + "&limit=1&format=json&q="
		self.google_api_apiurl = "https://maps.googleapis.com/maps/api/geocode/json?key=" + self.google_apikey + "&address="

	def get_coords(self, the_geoloc, api):
		if len(the_geoloc["city"]) == 0:
			query = str(the_geoloc["cp"]) + " France"
		elif the_geoloc["cp"] == 0:
			query = the_geoloc["city"] + " France"
		else:
			query = the_geoloc["city"] + " " + str(the_geoloc["cp"]) + " France"
		
		if api == "mapquest":
			try:
				data = requests.get(self.mapquest_api_url + query)
				if data.json() and len(data.json()) == 0:
					return {'lon': '', 'lat': ''}
				else:
					if data.json()[0]:
						return {'lon': data.json()[0]['lon'], 'lat': data.json()[0]['lat']}
					return {'lon': '', 'lat': ''}
			except Exception as e:
				print(e, data)
				return None
		
		elif api == "google":
			try:
				data = requests.get(self.google_api_apiurl + query)	
				if data.json() and data.json()['status'] == 'OVER_QUERY_LIMIT':
					print('OVER_QUERY_LIMIT')
					sys.exit()

				if data.json() and data.json()['status'] != 'OK':
					print data.json()['status']
					return {'lon': '', 'lat': ''}
				else:
					location = data.json()['results'][0]['geometry']['location']
					return {'lon': location['lng'], 'lat': location['lat']}
			except Exception as e:
				print(e, data)
				return None

			# return {'lon': 5.1274645, 'lat': 45.6846757}


	def get_products_to_update(self):		
		query = self.session_instance.query(Product)\
		.filter(or_(Product.lon == None, Product.lat == None))\
		.order_by(Product.published_at.desc())
		res = query.all()
		if len(res) == 0:
			return None		
		return res

	def update_lon_lat(self, product):
		coords = self.get_coords({'city': product.city, 'cp': product.cp}, self.active_api)				
		if coords is not None:			
			product.lon, product.lat = coords['lon'], coords['lat']			
			print "--updated product {0}".format(product.id)
			self.session_instance.commit()			

	def update(self):
		print "Update Started..."
		products = self.get_products_to_update()
		if products is None:
			return False

		for product in products:
			self.update_lon_lat(product)
			time.sleep(10)

if __name__ == '__main__':
	n = Normalizer()
	n.update()