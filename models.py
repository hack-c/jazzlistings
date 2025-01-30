from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import ARRAY
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
    """
    Artist model represents a musical artist.
    """

    __tablename__ = 'artists'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    concerts = relationship(
        'Concert', secondary=concert_artists, back_populates='artists'
    )


class Venue(Base):
    """
    Venue model represents a concert venue.
    """

    __tablename__ = 'venues'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    website_url = Column(String)
    concerts = relationship('Concert', back_populates='venue')


class Concert(Base):
    """
    Concert model represents a concert event.
    """

    __tablename__ = 'concerts'
    id = Column(Integer, primary_key=True)
    venue_id = Column(Integer, ForeignKey('venues.id'), nullable=False)
    times = Column(ARRAY(DateTime), nullable=False)
    ticket_link = Column(String)
    price_range = Column(String)
    special_notes = Column(Text)
    venue = relationship('Venue', back_populates='concerts')
    artists = relationship(
        'Artist', secondary=concert_artists, back_populates='concerts'
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
