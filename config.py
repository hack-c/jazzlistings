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

    # Database URL (Using SQLite for simplicity)
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///concerts.db')

except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise
