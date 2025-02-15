import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def scrape_ra(url):
    """Scrape a Resident Advisor venue page for events."""
    logging.info("Fetching RA calendar")
    
    # More complete browser headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'DNT': '1',
        'Cache-Control': 'max-age=0',
    }
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    try:
        # Add a small random delay
        time.sleep(random.uniform(2, 4))
        
        # First, get the main page to set cookies
        response = session.get('https://ra.co', headers=headers)
        response.raise_for_status()
        
        # Small delay before next request
        time.sleep(random.uniform(1, 2))
        
        # Now get the venue page
        response = session.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            logging.error("Could not find __NEXT_DATA__ script")
            logging.debug(f"Page content: {response.text[:500]}")  # Log first 500 chars for debugging
            return []
            
        data = json.loads(next_data_script.string)
        apollo_state = data["props"]["apolloState"]
        
        events = []
        for key, value in apollo_state.items():
            if key.startswith("Event:") and value.get("__typename") == "Event":
                try:
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
                    logging.debug(f"Extracted: {artist_str} on {event_date}")
                    
                except Exception as e:
                    logging.error(f"Error processing event: {e}")
                    continue
                    
        logging.info(f"Found {len(events)} events")
        return events
        
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error scraping RA page: {e.response.status_code} - {e.response.reason}")
        if e.response.status_code == 403:
            logging.error("Access forbidden - RA may be blocking our requests")
        return []
    except Exception as e:
        logging.error(f"Failed to scrape RA page: {e}")
        return []
    finally:
        session.close() 