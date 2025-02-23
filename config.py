import os
import logging

logger = logging.getLogger('concert_app')

# Firecrawl API Key
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# OpenAI API Key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Database URL (Using SQLite for simplicity)
DATABASE_URL = 'sqlite:///concerts.db'

# Only log configuration errors
try:
    # ... config loading ...
except Exception as e:
    logger.error(f"Configuration error: {e}")
