import re
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
import calendar
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def parse_date_range(date_range_str, default_year):
    """
    Given a date range string like 'February 11 – February 16' or 'February 25 - March 2',
    return (start_date, end_date) as datetime objects.
    """
    # Normalize various dash characters to a standard hyphen
    norm = date_range_str.replace("–", "-").replace("—", "-").strip()
    parts = norm.split("-")
    if len(parts) == 1:
        start_str = parts[0].strip()
        end_str = start_str
    else:
        start_str = parts[0].strip()
        end_str = parts[1].strip()
    
    try:
        start_date = dateparser.parse(f"{start_str} {default_year}")
    except Exception as e:
        logging.error(f"Error parsing start date '{start_str}': {e}")
        start_date = None

    if re.search(r"[A-Za-z]", end_str):
        try:
            end_date = dateparser.parse(f"{end_str} {default_year}")
        except Exception as e:
            logging.error(f"Error parsing end date '{end_str}': {e}")
            end_date = None
    else:
        try:
            month = start_date.strftime("%B")
            end_date = dateparser.parse(f"{month} {end_str} {default_year}")
        except Exception as e:
            logging.error(f"Error parsing end date with month '{month} {end_str}': {e}")
            end_date = None

    return start_date, end_date

def daterange(start_date, end_date):
    """Yield each date from start_date to end_date inclusive."""
    for n in range((end_date - start_date).days + 1):
        yield start_date + timedelta(n)

def scrape_events(html):
    """Parse events from Village Vanguard HTML"""
    soup = BeautifulSoup(html, "html.parser")
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
            start_date, end_date = parse_date_range(date_text, datetime.now().year)
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
            
    return events

def scrape_vanguard():
    """Main function to scrape Village Vanguard website"""
    try:
        url = "https://villagevanguard.com/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        events = scrape_events(response.text)
        if not events:
            logging.warning("No events found on Village Vanguard website")
        else:
            logging.info(f"Found {len(events)} events at Village Vanguard")
            
        return events

    except requests.RequestException as e:
        logging.error(f"Error fetching Village Vanguard website: {e}")
        return []
    except Exception as e:
        logging.error(f"Error scraping Village Vanguard: {e}")
        return []

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Test the scraper
    events = scrape_vanguard()
    print(json.dumps(events, indent=2)) 