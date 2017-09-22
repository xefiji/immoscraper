from sqlalchemy import create_engine, Column, Integer, String, DateTime, UnicodeText, BigInteger, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine.url import URL
import datetime

import settings

DeclarativeBase = declarative_base()


def db_connect():
    cnx = "{0}://{1}:{2}@{3}/{4}?charset={5}".format(settings.DATABASE['drivername'], settings.DATABASE['username'],
                                                     settings.DATABASE['password'], settings.DATABASE['host'],
                                                     settings.DATABASE['database'], settings.DATABASE['charset'])
    return create_engine(cnx)


def create_product_table(engine):
    DeclarativeBase.metadata.create_all(engine)


class Product(DeclarativeBase):
    """Sqlalchemy Product model"""
    __tablename__ = "product_2"
    id = Column(Integer, primary_key=True)
    category = Column('category', String(255))
    city = Column('city', String(255), nullable=True)
    cp = Column('cp', Integer, nullable=True)
    lon = Column('lon', Float, nullable=True)
    lat = Column('lat', Float, nullable=True)
    created_at = Column('created_at', DateTime, default=datetime.datetime.now)
    published_at = Column('published_at', DateTime, nullable=True)
    desc = Column('desc', UnicodeText(convert_unicode=False), nullable=True)
    href = Column('href', String(255), nullable=True)
    img = Column('img', String(255), nullable=True)
    name = Column('name', String(255), nullable=True)
    origin = Column('origin', String(255), nullable=True)
    price = Column('price', Integer, nullable=True)
    ref = Column('ref', BigInteger, nullable=True)
    status = Column('status', String(255), nullable=True, default='active')
    updated_at = Column('updated_at', DateTime, nullable=True)
    surface = Column('surface', String(255), nullable=True)
    rooms = Column('rooms', String(255), nullable=True)
    type = Column('type', String(255), nullable=True)
    version = Column('version', String(255), nullable=True, default=1)
    alert_sent = Column('alert_sent', String(255), nullable=True, default=0)
