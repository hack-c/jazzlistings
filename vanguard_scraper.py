import re
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
import calendar
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_date_range(date_range_str, default_year):
    """Parse a date range string into start and end dates."""
    norm = date_range_str.replace("–", "-").replace("—", "-").strip()
    parts = norm.split("-")
    start_str = parts[0].strip()
    end_str = parts[1].strip() if len(parts) > 1 else start_str
    
    try:
        start_date = dateparser.parse(f"{start_str} {default_year}")
    except Exception:
        start_date = None

    if re.search(r"[A-Za-z]", end_str):
        try:
            end_date = dateparser.parse(f"{end_str} {default_year}")
        except Exception:
            end_date = None
    else:
        try:
            month = start_date.strftime("%B")
            end_date = dateparser.parse(f"{month} {end_str} {default_year}")
        except Exception:
            end_date = None

    return start_date, end_date

def daterange(start_date, end_date):
    """Generate dates between start_date and end_date."""
    for n in range((end_date - start_date).days + 1):
        yield start_date + timedelta(n)

def scrape_vanguard():
    """Scrape the Village Vanguard website for events."""
    url = "https://villagevanguard.com/"
    logging.info("Fetching Village Vanguard calendar")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the container with the events
        article = soup.find("article", id="upcoming")
        if not article:
            logging.error("Could not find the 'upcoming' article")
            return []
            
        ul = article.find("ul")
        if not ul:
            logging.error("Could not locate the events list")
            return []
            
        events = []
        current_year = datetime.now().year
        
        # Iterate over each event
        for li in ul.find_all("li", recursive=False):
            try:
                # ... processing code ...
                events.append(event)
                logging.debug(f"Extracted: {artist} on {date_formatted}")
                
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                continue
                
        logging.info(f"Found {len(events)} events")
        return events
        
    except Exception as e:
        logging.error(f"Failed to scrape Village Vanguard: {e}")
        return [] 