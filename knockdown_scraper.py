import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_knockdown():
    """Scrape the Knockdown Center website for events."""
    url = "https://knockdown.center/upcoming/"
    logging.info("Fetching Knockdown Center calendar")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
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
        
        for li in ul.find_all("li", recursive=False):
            try:
                # Extract event title
                title_div = li.find("div", class_="eg-kdc2018-element-0-a")
                artist = title_div.get_text(strip=True) if title_div else ""
                
                # Extract date
                date_div = li.find("div", class_="eg-kdc2018-element-26")
                date_str = date_div.find("p").get_text(strip=True) if date_div and date_div.find("p") else ""
                
                # Parse date
                try:
                    parsed_date = datetime.strptime(f"{date_str} {current_year}", "%a %b %d %Y")
                    if parsed_date < datetime.now():
                        parsed_date = datetime.strptime(f"{date_str} {current_year + 1}", "%a %b %d %Y")
                    date_formatted = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    logging.warning(f"Could not parse date: {date_str}")
                    continue
                
                # Get ticket link
                ticket_link = ""
                buy_div = li.find("div", class_="eg-kdc2018-element-25-a")
                if buy_div:
                    a_buy = buy_div.find("a")
                    if a_buy and a_buy.has_attr("href"):
                        ticket_link = a_buy["href"]
                if not ticket_link and title_div:
                    a_event = title_div.find("a")
                    if a_event and a_event.has_attr("href"):
                        ticket_link = a_event["href"]
                
                event = {
                    "artist": artist,
                    "date": date_formatted,
                    "time": "10:00 PM",  # Default time
                    "ticket_link": ticket_link,
                    "special_notes": ""
                }
                events.append(event)
                logging.debug(f"Extracted: {artist} on {date_formatted}")
                
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                continue
                
        logging.info(f"Found {len(events)} events")
        return events
        
    except Exception as e:
        logging.error(f"Failed to scrape Knockdown Center: {e}")
        return [] 