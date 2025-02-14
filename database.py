from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import scoped_session
from config import DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a scoped session
SessionLocal = scoped_session(Session)

# Create a base class for declarative models
Base = declarative_base()

def init_db():
    """Initialize the database"""
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        
        print("Running database migrations...")
        
        # Create a single database session for all migrations
        db = SessionLocal()
        try:
            # Add columns if they don't exist
            from sqlalchemy import inspect
            inspector = inspect(engine)
            
            # Venue migrations
            existing_venue_columns = {col['name'] for col in inspector.get_columns('venues')}
            if 'neighborhood' not in existing_venue_columns:
                from migrations.add_venue_fields import upgrade as venue_upgrade
                venue_upgrade()
                print("Venue fields migration complete")
                
            if 'last_scraped' not in existing_venue_columns:
                from migrations.add_last_scraped import upgrade as scrape_upgrade
                scrape_upgrade()
                print("Last scraped migration complete")
            
            # User migrations
            existing_user_columns = {col['name'] for col in inspector.get_columns('users')}
            if 'preferred_venues' not in existing_user_columns:
                from migrations.add_user_preferences import upgrade as pref_upgrade
                pref_upgrade()
                print("User preferences migration complete")
            
            db.commit()
            
        except Exception as e:
            print(f"Migration error: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        print(f"Database initialization error: {e}")

def get_db():
    """Get a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
