import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def parse_date_range(date_text):
    """Parse date range like 'February 11 - February 16' into start and end dates"""
    current_year = datetime.now().year
    
    # Split on various dash types
    parts = re.split(r'[-–—]', date_text)
    if len(parts) == 2:
        start_str = parts[0].strip()
        end_str = parts[1].strip()
    else:
        start_str = date_text.strip()
        end_str = start_str
    
    try:
        start_date = datetime.strptime(f"{start_str} {current_year}", "%B %d %Y")
        end_date = datetime.strptime(f"{end_str} {current_year}", "%B %d %Y")
        
        # If dates are in the past, assume next year
        if start_date < datetime.now():
            start_date = datetime.strptime(f"{start_str} {current_year + 1}", "%B %d %Y")
            end_date = datetime.strptime(f"{end_str} {current_year + 1}", "%B %d %Y")
            
        return start_date, end_date
    except Exception as e:
        logging.error(f"Error parsing dates '{date_text}': {e}")
        return None, None

def scrape_vanguard():
    """Scrape the Village Vanguard website for events."""
    url = "https://villagevanguard.com"
    logging.info("Fetching Village Vanguard calendar")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        events = []
        
        # Find all event listings
        event_listings = soup.find_all("div", class_="event-listing")
        if not event_listings:
            logging.error("No event listings found")
            return []
            
        for listing in event_listings:
            try:
                # Get event title
                title = listing.find("h2")
                if not title:
                    continue
                artist = title.text.strip()
                
                # Get date range
                date_h3 = listing.find("h3")
                if not date_h3 or "event-tagline" in date_h3.get("class", []):
                    continue
                    
                date_text = date_h3.text.strip()
                start_date, end_date = parse_date_range(date_text)
                if not start_date or not end_date:
                    continue
                
                # Get ticket link
                ticket_link = ""
                ticket_btn = listing.find("a", class_="btn-primary")
                if ticket_btn:
                    ticket_link = ticket_btn["href"]
                
                # Get band members from event description
                band_members = []
                desc = listing.find("div", class_="event-short-description")
                if desc:
                    for member in desc.find_all("h4"):
                        if member.find("strong"):
                            name = member.find("strong").text.strip()
                            role = member.text.replace(name, "").strip(" -")
                            band_members.append(f"{name} ({role})")
                
                special_notes = "Band members: " + ", ".join(band_members) if band_members else ""
                
                # Create an event for each date in the range
                current = start_date
                while current <= end_date:
                    event = {
                        "artist": artist,
                        "date": current.strftime("%Y-%m-%d"),
                        "time": "8:00 PM",  # Default time for first set
                        "ticket_link": ticket_link,
                        "special_notes": special_notes
                    }
                    events.append(event)
                    current = current.replace(day=current.day + 1)
                    
                logging.debug(f"Extracted: {artist} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                
            except Exception as e:
                logging.error(f"Error processing event listing: {e}")
                continue
                
        logging.info(f"Found {len(events)} events")
        return events
        
    except Exception as e:
        logging.error(f"Failed to scrape Village Vanguard: {e}")
        return [] 