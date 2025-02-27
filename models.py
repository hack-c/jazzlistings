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
    UniqueConstraint,
    Boolean,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from base import Base

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
    neighborhood = Column(String)
    genres = Column(JSON, default=list)  # Store multiple genres as a JSON array
    # Note: PostgreSQL will use JSONB type for better performance
    last_scraped = Column(DateTime(timezone=True))  # New column

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    spotify_token = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Add preference columns with default empty lists
    preferred_venues = Column(JSON, default=lambda: [], nullable=False)
    preferred_genres = Column(JSON, default=lambda: [], nullable=False)
    preferred_neighborhoods = Column(JSON, default=lambda: [], nullable=False)
    
    # Relationship to track favorite concerts
    favorite_concerts = relationship(
        'Concert',
        secondary='user_favorites',
        back_populates='favorited_by'
    )

# Association table for user favorites
user_favorites = Table(
    'user_favorites',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('concert_id', Integer, ForeignKey('concerts.id'), primary_key=True)
)

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
    favorited_by = relationship(
        'User',
        secondary='user_favorites',
        back_populates='favorite_concerts'
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # NOTE: UniqueConstraint was originally on venue_id + date only, 
    # which was preventing multiple events at the same venue on the same day.
    # For now, we're logging this issue; we'll remove/modify this constraint after validating.

class ConcertTime(Base):
    __tablename__ = 'concert_times'
    
    id = Column(Integer, primary_key=True)
    concert_id = Column(Integer, ForeignKey('concerts.id'))
    time = Column(Time, nullable=True)
    
    concert = relationship('Concert', back_populates='times')
