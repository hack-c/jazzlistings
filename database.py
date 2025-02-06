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
    """
    Initialize the database by creating all tables.
    """
    Base.metadata.create_all(engine)

def get_db():
    """Get a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
