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
    logging.info(f"Fetching Village Vanguard calendar from {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text
    except Exception as e:
        logging.error(f"Failed to fetch Village Vanguard page: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # Get default year from ticket links
    ticket_link = soup.find("a", class_="btn btn-primary")
    default_year = datetime.now().year
    if ticket_link:
        m = re.search(r"(\d{4})", ticket_link.get("href", ""))
        if m:
            default_year = m.group(1)
    
    event_listings = soup.find_all("div", class_="event-listing")
    logging.info(f"Found {len(event_listings)} event listings")
    
    for listing in event_listings:
        try:
            title_tag = listing.find("h2")
            if not title_tag:
                continue
            title_text = title_tag.get_text(strip=True)
            
            # Handle recurring events (e.g., Monday night shows)
            recurring_tag = listing.find("h3", class_="event-tagline")
            if recurring_tag:
                # Process recurring event...
                recurring_text = recurring_tag.get_text(strip=True)
                m_recurring = re.search(r"Every\s+(\w+)", recurring_text, re.IGNORECASE)
                if m_recurring:
                    weekday_str = m_recurring.group(1)
                    try:
                        target_weekday_index = list(calendar.day_name).index(weekday_str.capitalize())
                        current_date = datetime.now().date()
                        end_date = current_date + timedelta(days=60)
                        days_ahead = (target_weekday_index - current_date.weekday()) % 7
                        first_occurrence = current_date + timedelta(days=days_ahead)
                        
                        # Get band info
                        event_short = listing.find("div", class_="event-short-description")
                        band_members = []
                        if event_short:
                            for h4 in event_short.find_all("h4"):
                                strong = h4.find("strong")
                                if strong:
                                    member_name = strong.get_text(strip=True)
                                    remaining = h4.get_text().replace(member_name, "").strip()
                                    remaining = re.sub(r"^[-–—\s]+", "", remaining)
                                    if remaining:
                                        band_members.append(f"{member_name} ({remaining})")
                                    else:
                                        band_members.append(member_name)
                                        
                        special_notes = "Band members: " + ", ".join(band_members) if band_members else ""
                        ticket_a = listing.find("a", class_="btn btn-primary")
                        ticket_href = ticket_a["href"] if ticket_a else ""
                        
                        # Create events for each occurrence
                        date_iter = first_occurrence
                        while date_iter <= end_date:
                            events.append({
                                "artist": title_text,
                                "date": date_iter.strftime("%Y-%m-%d"),
                                "time": "8:00 PM",  # Default time
                                "ticket_link": ticket_href,
                                "special_notes": special_notes
                            })
                            date_iter += timedelta(days=7)
                        continue
            
            # Handle normal events
            h3_tags = listing.find_all("h3")
            date_range_text = None
            for h3 in h3_tags:
                if "event-tagline" not in h3.get("class", []) and re.search(r"\d", h3.get_text()):
                    date_range_text = h3.get_text(strip=True)
                    break
                    
            if not date_range_text:
                continue
                
            start_date, end_date = parse_date_range(date_range_text, default_year)
            if not (start_date and end_date):
                continue
                
            # Get band info
            event_short = listing.find("div", class_="event-short-description")
            band_members = []
            if event_short:
                for h4 in event_short.find_all("h4"):
                    strong = h4.find("strong")
                    if strong:
                        member_name = strong.get_text(strip=True)
                        remaining = h4.get_text().replace(member_name, "").strip()
                        remaining = re.sub(r"^[-–—\s]+", "", remaining)
                        if remaining:
                            band_members.append(f"{member_name} ({remaining})")
                        else:
                            band_members.append(member_name)
                            
            special_notes = "Band members: " + ", ".join(band_members) if band_members else ""
            ticket_a = listing.find("a", class_="btn btn-primary")
            ticket_href = ticket_a["href"] if ticket_a else ""
            
            # Create events for each date in the range
            for single_date in daterange(start_date, end_date):
                events.append({
                    "artist": title_text,
                    "date": single_date.strftime("%Y-%m-%d"),
                    "time": "8:00 PM",  # Default time
                    "ticket_link": ticket_href,
                    "special_notes": special_notes
                })
                
        except Exception as e:
            logging.error(f"Error processing event listing: {e}")
            continue
            
    logging.info(f"Successfully scraped {len(events)} events from Village Vanguard")
    return events 