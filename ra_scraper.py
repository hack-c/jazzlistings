import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logging

logger = logging.getLogger('concert_app')

def scrape_ra(url):
    """Scrape event data from RA using their Next.js data"""
    try:
        logger.info(f"Scraping RA: {url}")
        
        # Set up Chrome
        chrome_options = Options()
        
        # Fetch the page
        logger.info("Fetching page with Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        html = driver.page_source
        driver.quit()
        
        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract the __NEXT_DATA__ JSON
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            logger.error("Could not find __NEXT_DATA__ script")
            return []
            
        data = json.loads(next_data_script.string)
        
        # Get the Apollo state that holds all our cached objects
        apollo_state = data["props"]["apolloState"]
        
        events = []
        
        for key, value in apollo_state.items():
            # Process only objects that are events
            if key.startswith("Event:") and value.get("__typename") == "Event":
                event = value
                
                # Format date (YYYY-MM-DD)
                event_date = event.get("date", "")[:10]
                
                # Extract and format the start time to "HH:MM"
                start_time_iso = event.get("startTime", "")
                time_formatted = ""
                if start_time_iso:
                    try:
                        dt = datetime.fromisoformat(start_time_iso)
                        time_formatted = dt.strftime("%H:%M")
                    except Exception as e:
                        logger.warning(f"Error parsing time {start_time_iso}: {e}")
                        time_formatted = start_time_iso[11:16]
                
                # Get artist names by following the __ref pointers
                artist_names = []
                for artist_ref in event.get("artists", []):
                    ref_key = artist_ref.get("__ref")
                    if ref_key and ref_key in apollo_state:
                        artist_obj = apollo_state[ref_key]
                        name = artist_obj.get("name")
                        if name:
                            artist_names.append(name)
                artist_str = ", ".join(artist_names)
                
                # Get venue details
                venue_name = ""
                venue_address = ""
                venue_ref = event.get("venue", {}).get("__ref")
                if venue_ref and venue_ref in apollo_state:
                    venue_obj = apollo_state[venue_ref]
                    venue_name = venue_obj.get("name", "")
                    venue_address = venue_obj.get("address", "")
                
                # Build ticket link
                content_url = event.get("contentUrl", "")
                ticket_link = "https://ra.co" + content_url
                
                # Build the event dict
                event_dict = {
                    "artist": artist_str,
                    "date": event_date,
                    "times": [time_formatted] if time_formatted else [],
                    "venue": venue_name,
                    "address": venue_address,
                    "ticket_link": ticket_link,
                    "price_range": None,
                    "special_notes": ""
                }
                events.append(event_dict)
                logger.debug(f"Extracted event: {event_dict}")
        
        logger.info(f"Found {len(events)} events")
        return events
        
    except Exception as e:
        logger.error(f"Error scraping RA: {e}")
        logger.exception(e)  # Log full traceback
        return [] 