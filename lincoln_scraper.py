import re
import json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict
import logging

def scrape_lincoln():
    """Scrape Film at Lincoln Center's schedule"""
    URL = "https://www.filmlinc.org/"
    logging.info("Fetching Film at Lincoln Center schedule")
    
    try:
        # Create a CloudScraper session to bypass 403 errors
        scraper = cloudscraper.create_scraper()
        response = scraper.get(URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Locate the FilmLinc JSON data
        script_tag = soup.find("script", text=re.compile(r"var\s+FilmLinc\s*="))
        if not script_tag:
            logging.error("Could not find the FilmLinc JSON data")
            return []
            
        # Extract the JSON
        match = re.search(r"var\s+FilmLinc\s*=\s*(\{.*?\});", script_tag.string, re.DOTALL)
        if not match:
            logging.error("Could not extract FilmLinc JSON")
            return []
            
        filmLinc_json_str = match.group(1)
        data = json.loads(filmLinc_json_str)
        
        # Consolidate showings by (film title, date)
        consolidated = defaultdict(lambda: {
            "artist": None,
            "date": None,
            "times": set(),  # Use set to avoid duplicates
            "venue": None,
            "address": "10 Lincoln Center Plaza, New York, NY 10023",
            "ticket_link": None,
            "price_range": None,
            "special_notes": None
        })
        
        # Process each showing
        for showing in data.get("showings", []):
            try:
                film = showing.get("display_name", "").strip()
                event_date_str = showing.get("event_date", "")
                
                try:
                    dt = datetime.strptime(event_date_str, "%Y-%m-%d %H:%M:%S")
                    date_key = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H:%M")
                except Exception as e:
                    logging.error(f"Error parsing date '{event_date_str}': {e}")
                    continue
                    
                key = (film, date_key)
                entry = consolidated[key]
                entry["artist"] = film
                entry["date"] = date_key
                entry["times"].add(time_str)
                
                if not entry["venue"]:
                    entry["venue"] = showing.get("venue_name", "").strip()
                if not entry["ticket_link"]:
                    entry["ticket_link"] = showing.get("event_url", "").strip()
                if not entry["special_notes"]:
                    entry["special_notes"] = showing.get("desc", "").strip()
                    
            except Exception as e:
                logging.error(f"Error processing showing: {e}")
                continue
                
        # Convert times set to sorted list and prepare results
        results = []
        for entry in consolidated.values():
            entry["times"] = sorted(list(entry["times"]))
            results.append(entry)
            
        logging.info(f"Found {len(results)} film showings at Lincoln Center")
        return results
        
    except Exception as e:
        logging.error(f"Error scraping Film at Lincoln Center: {e}")
        return []

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Test the scraper
    showtimes = scrape_lincoln()
    for show in showtimes:
        print(show) 