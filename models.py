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

Base = declarative_base()

# Association table between Concerts and Artists (Many-to-Many relationship)
concert_artists = Table(
    'concert_artists',
    Base.metadata,
    Column('concert_id', Integer, ForeignKey('concerts.id')),
    Column('artist_id', Integer, ForeignKey('artists.id')),
)

class Artist(Base):
    __tablename__ = 'artists'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    concerts = relationship(
        'Concert', secondary=concert_artists, back_populates='artists'
    )

class Venue(Base):
    __tablename__ = 'venues'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    website_url = Column(String)
    concerts = relationship('Concert', back_populates='venue')

class ConcertTime(Base):
    __tablename__ = 'concert_times'
    id = Column(Integer, primary_key=True)
    concert_id = Column(Integer, ForeignKey('concerts.id'))
    time = Column(Time, nullable=True)

    concert = relationship('Concert', back_populates='times')

class Concert(Base):
    __tablename__ = 'concerts'
    id = Column(Integer, primary_key=True)
    artist = Column(String)
    date = Column(Date, nullable=False)
    venue = Column(String)
    address = Column(String)
    ticket_link = Column(String)
    price_range = Column(String)
    special_notes = Column(String)

    times = relationship('ConcertTime', back_populates='concert', cascade="all, delete-orphan")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
