import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_ra(url):
    """Scrape a Resident Advisor venue page for events."""
    logging.info(f"Fetching RA calendar from {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/87.0.4280.66 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            logging.error("__NEXT_DATA__ script tag not found")
            return []
            
        data = json.loads(next_data_script.string)
        apollo_state = data["props"]["apolloState"]
        
        events = []
        for key, value in apollo_state.items():
            if key.startswith("Event:") and value.get("__typename") == "Event":
                event = value
                
                # Format date
                event_date = event.get("date", "")[:10]
                
                # Extract and format time
                start_time_iso = event.get("startTime", "")
                time_formatted = ""
                if start_time_iso:
                    try:
                        dt = datetime.fromisoformat(start_time_iso)
                        time_formatted = dt.strftime("%H:%M")
                    except Exception:
                        time_formatted = start_time_iso[11:16]
                
                # Get artist names
                artist_names = []
                for artist_ref in event.get("artists", []):
                    ref_key = artist_ref.get("__ref")
                    if ref_key and ref_key in apollo_state:
                        artist_obj = apollo_state[ref_key]
                        name = artist_obj.get("name")
                        if name:
                            artist_names.append(name)
                artist_str = ", ".join(artist_names) or event.get("title", "")
                
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
                
                event_dict = {
                    "artist": artist_str,
                    "date": event_date,
                    "time": time_formatted,
                    "ticket_link": ticket_link,
                    "special_notes": ""
                }
                events.append(event_dict)
                logging.info(f"Extracted event: {artist_str} on {event_date}")
                
        logging.info(f"Successfully scraped {len(events)} events from RA")
        return events
        
    except Exception as e:
        logging.error(f"Failed to scrape RA page: {e}")
        return [] 