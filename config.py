import os
import logging

logger = logging.getLogger('concert_app')

# Only log configuration errors
try:
    # Firecrawl API Key
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
    if not FIRECRAWL_API_KEY:
        logger.warning('FIRECRAWL_API_KEY not set')

    # OpenAI API Key
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY not set')

    # Database URL
    # Use DATABASE_URL directly if provided, otherwise construct from individual params
    if os.getenv('DATABASE_URL'):
        DATABASE_URL = os.getenv('DATABASE_URL')
    else:
        # Build PostgreSQL connection string from individual environment variables
        db_user = os.getenv('PGUSER')
        db_password = os.getenv('PGPASSWORD')
        db_host = os.getenv('PGHOST')
        db_port = os.getenv('PGPORT', '5432')
        db_name = os.getenv('PGDATABASE')
        
        if all([db_user, db_password, db_host, db_name]):
            DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            # Fallback to SQLite
            logger.warning('PostgreSQL credentials incomplete - falling back to SQLite')
            DATABASE_URL = 'sqlite:///concerts.db'

except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise
