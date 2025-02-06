# models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    Text,
    create_engine,
    Date,
    Time,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from database import Base

# Association table for many-to-many relationship between concerts and artists
concert_artists = Table(
    'concert_artists',
    Base.metadata,
    Column('concert_id', Integer, ForeignKey('concerts.id'), primary_key=True),
    Column('artist_id', Integer, ForeignKey('artists.id'), primary_key=True)
)

class Artist(Base):
    __tablename__ = 'artists'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    # Relationship to concerts
    concerts = relationship('Concert', 
                          secondary=concert_artists,
                          back_populates='artists')

class Venue(Base):
    __tablename__ = 'venues'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    website_url = Column(String)

class Concert(Base):
    __tablename__ = 'concerts'
    
    id = Column(Integer, primary_key=True)
    venue_id = Column(Integer, ForeignKey('venues.id'))
    date = Column(Date, nullable=False)
    ticket_link = Column(String)
    price_range = Column(String)
    special_notes = Column(String)
    
    # Relationships
    venue = relationship('Venue')
    artists = relationship('Artist',
                         secondary=concert_artists,
                         back_populates='concerts')
    times = relationship('ConcertTime', back_populates='concert', cascade='all, delete-orphan')
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ConcertTime(Base):
    __tablename__ = 'concert_times'
    
    id = Column(Integer, primary_key=True)
    concert_id = Column(Integer, ForeignKey('concerts.id'))
    time = Column(Time, nullable=True)
    
    concert = relationship('Concert', back_populates='times')
