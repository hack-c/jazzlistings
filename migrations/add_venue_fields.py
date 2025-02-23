from database import SessionLocal, engine
from sqlalchemy import Column, String, JSON
from models import Venue
from alembic import op
import sqlalchemy as sa
import logging

def upgrade():
    with op.batch_alter_table('venues') as batch_op:
        batch_op.add_column(Column('neighborhood', String))
        batch_op.add_column(Column('genres', JSON))

    # Populate with initial data
    db = SessionLocal()
    try:
        # Define known venue neighborhoods and genres
        venue_data = {
            # Movie Theaters
            'IFC Center': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Movies']
            },
            'Film Forum': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Movies']
            },
            'Quad Cinema': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Movies']
            },
            'Film at Lincoln Center': {
                'neighborhood': 'Upper West Side',
                'genres': ['Movies']
            },
            
            # Clubs (Electronic/Dance)
            'Mansions': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Jupiter Disco': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Bossa Nova Civic Club': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'House of Yes': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Elsewhere': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Good Room': {
                'neighborhood': 'Greenpoint',
                'genres': ['Clubs']
            },
            'Nowadays': {
                'neighborhood': 'Ridgewood',
                'genres': ['Clubs']
            },
            'Public Records': {
                'neighborhood': 'Gowanus',
                'genres': ['Clubs']
            },
            'The Sultan Room': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Black Flamingo': {
                'neighborhood': 'Williamsburg',
                'genres': ['Clubs']
            },
            '3 Dollar Bill': {
                'neighborhood': 'East Williamsburg',
                'genres': ['Clubs']
            },
            'Knockdown Center': {
                'neighborhood': 'Maspeth',
                'genres': ['Clubs', 'Galleries']
            },

            # Jazz Venues
            'Village Vanguard': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Blue Note': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Smalls Jazz Club': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Mezzrow Jazz Club': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Dizzy\'s Club': {
                'neighborhood': 'Columbus Circle',
                'genres': ['Jazz']
            },
            'The Jazz Gallery': {
                'neighborhood': 'Flatiron',
                'genres': ['Jazz']
            },
            'Birdland': {
                'neighborhood': 'Theater District',
                'genres': ['Jazz']
            },
            'Close Up': {
                'neighborhood': 'Lower East Side',
                'genres': ['Jazz']
            },
            'Bar LunÀtico': {
                'neighborhood': 'Bedford-Stuyvesant',
                'genres': ['Jazz']
            },
            'Bar Bayeux': {
                'neighborhood': 'Prospect Heights',
                'genres': ['Jazz']
            },
            'Marians Jazz Room': {
                'neighborhood': 'Williamsburg',
                'genres': ['Jazz']
            },
            'The Owl Music Parlor': {
                'neighborhood': 'Prospect Heights',
                'genres': ['Jazz']
            },
            'Zinc Bar': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Mona\'s': {
                'neighborhood': 'East Village',
                'genres': ['Jazz']
            },
            'The Stone': {
                'neighborhood': 'East Village',
                'genres': ['Jazz']
            },
            'Ornithology Jazz Club': {
                'neighborhood': 'Bushwick',
                'genres': ['Jazz']
            },
            'Ornithology Cafe': {
                'neighborhood': 'Bushwick',
                'genres': ['Jazz']
            },
            'Smoke Jazz & Supper Club': {
                'neighborhood': 'Upper West Side',
                'genres': ['Jazz']
            },
            'Room 623 at B2 Harlem': {
                'neighborhood': 'Harlem',
                'genres': ['Jazz']
            },
            'Minton\'s Playhouse': {
                'neighborhood': 'Harlem',
                'genres': ['Jazz']
            },

            # Mixed Genre Venues
            'Roulette': {
                'neighborhood': 'Downtown Brooklyn',
                'genres': ['Jazz', 'Galleries']
            },
            'National Sawdust': {
                'neighborhood': 'Williamsburg',
                'genres': ['Jazz', 'Classical']
            },
            'Le Poisson Rouge': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Drom': {
                'neighborhood': 'East Village',
                'genres': ['Jazz']
            },
            'The Django': {
                'neighborhood': 'Tribeca',
                'genres': ['Jazz']
            },
            'Joe\'s Pub': {
                'neighborhood': 'NoHo',
                'genres': ['Jazz']
            },
            'Symphony Space': {
                'neighborhood': 'Upper West Side',
                'genres': ['Classical']
            },
            'The Cutting Room': {
                'neighborhood': 'Flatiron',
                'genres': ['Jazz', 'Clubs']
            },
            'Nublu 151': {
                'neighborhood': 'East Village',
                'genres': ['Jazz']
            }
        }

        # First, update existing venues
        for venue in db.query(Venue).all():
            if venue.name in venue_data:
                venue.neighborhood = venue_data[venue.name]['neighborhood']
                venue.genres = venue_data[venue.name]['genres']
                logging.info(f"Updated existing venue: {venue.name}")
            else:
                logging.warning(f"No data found for existing venue: {venue.name}")

        # Then, add any missing venues
        existing_venues = {venue.name for venue in db.query(Venue).all()}
        for name, data in venue_data.items():
            if name not in existing_venues:
                new_venue = Venue(
                    name=name,
                    neighborhood=data['neighborhood'],
                    genres=data['genres'],
                    website_url=None  # You might want to add website URLs to venue_data
                )
                db.add(new_venue)
                logging.info(f"Added new venue: {name}")
        
        db.commit()
        print("Successfully updated venue data")
        
        # Verify the update
        for venue in db.query(Venue).all():
            print(f"Venue: {venue.name}, Neighborhood: {venue.neighborhood}, Genres: {venue.genres}")
        
    except Exception as e:
        print(f"Error updating venue data: {e}")
        db.rollback()
    finally:
        db.close()

def downgrade():
    with op.batch_alter_table('venues') as batch_op:
        batch_op.drop_column('neighborhood')
        batch_op.drop_column('genres') 