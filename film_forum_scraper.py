import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging

def scrape_film_forum():
    """Scrape Film Forum's Now Playing schedule"""
    URL = "https://filmforum.org/now_playing"
    logging.info("Fetching Film Forum schedule")
    
    try:
        # Fetch the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Get today's date
        today = datetime.today().date()
        
        # Find tabs container
        tabs_container = soup.find("div", id="tabs")
        if not tabs_container:
            logging.error("Could not find tabs container")
            return []
            
        # Find and sort tabs
        tabs = tabs_container.find_all("div", id=lambda x: x and x.startswith("tabs-"))
        sorted_tabs = sorted(tabs, key=lambda div: int(div.get("id").split("-")[-1]))
        
        # Process each tab/day
        for i, tab_div in enumerate(sorted_tabs):
            try:
                date_for_tab = (today + timedelta(days=i)).strftime("%Y-%m-%d")
                
                # Process each film entry
                for p in tab_div.find_all("p"):
                    try:
                        # Get film title and link
                        strong = p.find("strong")
                        if not strong:
                            continue
                        film_a = strong.find("a")
                        if not film_a:
                            continue
                            
                        film_title = film_a.get_text(" ", strip=True)
                        ticket_link = film_a.get("href")
                        
                        # Check if it's Film Forum Jr
                        a_tags = p.find_all("a")
                        is_jr = False
                        if a_tags and len(a_tags) > 1:
                            if a_tags[0].get_text(strip=True).upper() == "FILM FORUM JR.":
                                is_jr = True
                        
                        # Get special notes
                        special_span = p.find("span", class_="alert")
                        special_notes = special_span.get_text(strip=True) if special_span else ""
                        
                        # Get showtimes
                        time_spans = p.find_all("span")
                        for span in time_spans:
                            if span.get("class") and "alert" in span.get("class"):
                                continue
                                
                            raw_time = span.get_text(strip=True)
                            if not raw_time:
                                continue
                                
                            try:
                                # Parse time
                                dt_time = datetime.strptime(raw_time, "%I:%M")
                                hour = dt_time.hour
                                minute = dt_time.minute
                                
                                # Adjust for PM times
                                if not is_jr and hour < 12 and hour != 0:
                                    hour += 12
                                    
                                time_formatted = f"{hour:02d}:{minute:02d}"
                                
                                # Create event entry
                                event = {
                                    "artist": film_title,
                                    "date": date_for_tab,
                                    "time": time_formatted,
                                    "ticket_link": ticket_link,
                                    "special_notes": special_notes
                                }
                                results.append(event)
                                
                            except Exception as e:
                                logging.error(f"Error parsing time '{raw_time}': {e}")
                                continue
                                
                    except Exception as e:
                        logging.error(f"Error processing film entry: {e}")
                        continue
                        
            except Exception as e:
                logging.error(f"Error processing tab for day {i}: {e}")
                continue
                
        logging.info(f"Found {len(results)} showtimes at Film Forum")
        return results
        
    except requests.RequestException as e:
        logging.error(f"Error fetching Film Forum website: {e}")
        return []
    except Exception as e:
        logging.error(f"Error scraping Film Forum: {e}")
        return []

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Test the scraper
    showtimes = scrape_film_forum()
    for show in showtimes:
        print(show) 