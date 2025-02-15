import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
import logging

def scrape_quad():
    """Scrape Quad Cinema's Now Playing schedule"""
    URL = "https://quadcinema.com"
    logging.info("Fetching Quad Cinema schedule")
    
    try:
        # Fetch the page
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        current_date = datetime.today()
        
        # Find all day schedules
        day_wraps = soup.find_all("div", class_="day-wrap")
        for day_div in day_wraps:
            try:
                # Get day number from class
                classes = day_div.get("class", [])
                date_day = None
                for cls in classes:
                    if cls.startswith("date-"):
                        try:
                            date_day = int(cls.split("-")[1])
                        except Exception:
                            continue
                        break
                        
                fallback_date = ""
                if date_day:
                    fallback_date = f"{current_date.year}-{current_date.month:02d}-{date_day:02d}"
                
                # Process each film
                grid_items = day_div.find_all("div", class_="grid-item")
                for item in grid_items:
                    try:
                        # Get film title
                        h4 = item.find("h4")
                        if not h4 or not h4.find("a"):
                            continue
                        film_title = h4.find("a").get_text(strip=True)
                        
                        # Get showtimes
                        ul = item.find("ul", class_="showtimes-list")
                        if not ul:
                            continue
                            
                        times_list = []
                        first_ticket_link = None
                        
                        # Process each showtime
                        for li in ul.find_all("li"):
                            a = li.find("a")
                            if not a:
                                continue
                                
                            raw_time = a.get_text(strip=True)
                            converted_time = raw_time.replace('.', ':')
                            try:
                                dt_time = datetime.strptime(converted_time, "%I:%M%p")
                                time_formatted = dt_time.strftime("%H:%M")
                            except Exception:
                                time_formatted = converted_time
                                
                            times_list.append(time_formatted)
                            if not first_ticket_link:
                                first_ticket_link = a.get("href")
                        
                        if not times_list:
                            continue
                            
                        # Get date from ticket link if available
                        date_str = fallback_date
                        if first_ticket_link:
                            parsed = urllib.parse.urlparse(first_ticket_link)
                            qs = urllib.parse.parse_qs(parsed.query)
                            if "date" in qs:
                                date_str = qs["date"][0]
                        
                        # Get special notes
                        special_div = item.find("div", class_="now-appearance")
                        special_notes = special_div.get_text(strip=True) if special_div else ""
                        
                        # Create event entry
                        event = {
                            "artist": film_title,
                            "date": date_str,
                            "times": times_list,
                            "ticket_link": first_ticket_link,
                            "special_notes": special_notes
                        }
                        results.append(event)
                        
                    except Exception as e:
                        logging.error(f"Error processing film: {e}")
                        continue
                        
            except Exception as e:
                logging.error(f"Error processing day: {e}")
                continue
                
        logging.info(f"Found {len(results)} showtimes at Quad Cinema")
        return results
        
    except requests.RequestException as e:
        logging.error(f"Error fetching Quad Cinema website: {e}")
        return []
    except Exception as e:
        logging.error(f"Error scraping Quad Cinema: {e}")
        return []

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Test the scraper
    showtimes = scrape_quad()
    for show in showtimes:
        print(show) 