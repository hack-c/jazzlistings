from database import SessionLocal, engine
from sqlalchemy import Column, String, JSON, text
from models import Venue
import logging
from sqlalchemy import inspect

def upgrade():
    db = SessionLocal()
    try:
        # First check if columns exist
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('venues')]
        
        # Add columns only if they don't exist
        with engine.begin() as conn:
            if 'neighborhood' not in columns:
                conn.execute(text("""
                    ALTER TABLE venues 
                    ADD COLUMN neighborhood VARCHAR;
                """))
                logging.info("Added neighborhood column")
                
            if 'genres' not in columns:
                conn.execute(text("""
                    ALTER TABLE venues 
                    ADD COLUMN genres JSON;
                """))
                logging.info("Added genres column")

        # Populate with initial data
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
                'genres': ['Jazz']         }
        }

        # Update venues, preserving any existing data
        for venue in db.query(Venue).all():
            if venue.name in venue_data:
                # Only update if fields are None/empty
                if not venue.neighborhood:
                    venue.neighborhood = venue_data[venue.name]['neighborhood']
                if not venue.genres:
                    venue.genres = venue_data[venue.name]['genres']
                logging.info(f"Updated venue: {venue.name} with neighborhood: {venue.neighborhood}")
            else:
                logging.warning(f"No data found for venue: {venue.name}")

        # Add any missing venues
        existing_venues = {venue.name for venue in db.query(Venue).all()}
        for name, data in venue_data.items():
            if name not in existing_venues:
                new_venue = Venue(
                    name=name,
                    neighborhood=data['neighborhood'],
                    genres=data['genres']
                )
                db.add(new_venue)
                logging.info(f"Added new venue: {name}")

        # Set default values for any remaining NULL fields
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE venues 
                SET neighborhood = 'Other'
                WHERE neighborhood IS NULL;
            """))
            conn.execute(text("""
                UPDATE venues 
                SET genres = '[]'
                WHERE genres IS NULL;
            """))

        db.commit()
        
        # Verify the update
        logging.info("Verifying venue data:")
        for venue in db.query(Venue).all():
            logging.info(f"Venue: {venue.name}, Neighborhood: {venue.neighborhood}, Genres: {venue.genres}")

    except Exception as e:
        logging.error(f"Error updating venue data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def downgrade():
    # Don't drop columns in production, just log
    logging.warning("Downgrade requested but skipped for safety in production") 