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
        # Import all migration modules
        from migrations import add_venue_fields, add_last_scraped, add_user_preferences
        
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        
        print("Running database migrations...")
        # Run migrations in order
        try:
            add_venue_fields.upgrade()
            print("Venue fields migration complete")
        except Exception as e:
            print(f"Venue fields migration warning: {e}")
            
        try:
            add_last_scraped.upgrade()
            print("Last scraped migration complete")
        except Exception as e:
            print(f"Last scraped migration warning: {e}")
            
        try:
            add_user_preferences.upgrade()
            print("User preferences migration complete")
        except Exception as e:
            print(f"User preferences migration warning: {e}")
            
    except Exception as e:
        print(f"Database initialization warning: {e}")
        # Tables might already exist, which is fine
        pass

def get_db():
    """Get a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
