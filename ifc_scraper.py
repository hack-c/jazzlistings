import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

def scrape_ifc():
    """Scrape IFC Center movie showtimes"""
    URL = "https://www.ifccenter.com/"
    logging.info("Fetching IFC Center schedule")
    
    try:
        # Fetch the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Iterate over each daily schedule container
        for schedule in soup.find_all("div", class_="daily-schedule"):
            try:
                # Get the date string
                date_header = schedule.find("h3")
                if not date_header:
                    continue
                    
                date_text = date_header.get_text(strip=True)
                # Use current year
                current_year = datetime.now().year
                full_date_str = f"{date_text} {current_year}"
                
                try:
                    dt = datetime.strptime(full_date_str, "%a %b %d %Y")
                    formatted_date = dt.strftime("%Y-%m-%d")
                except Exception as e:
                    logging.error(f"Error parsing date '{full_date_str}': {e}")
                    continue

                # Loop over each movie listing
                for li in schedule.find_all("li"):
                    details = li.find("div", class_="details")
                    if not details:
                        continue

                    title_elem = details.find("h3")
                    if not title_elem or not title_elem.find("a"):
                        continue
                    movie_name = title_elem.find("a").get_text(strip=True)

                    # Get showtimes
                    times_ul = details.find("ul", class_="times")
                    if times_ul:
                        for time_li in times_ul.find_all("li"):
                            a_tag = time_li.find("a")
                            if a_tag:
                                raw_time = a_tag.get_text(strip=True)
                                try:
                                    dt_time = datetime.strptime(raw_time, "%I:%M %p")
                                    time_formatted = dt_time.strftime("%I:%M %p")
                                except Exception:
                                    time_formatted = raw_time
                                    
                                ticket_link = a_tag.get("href")
                                
                                movie_show = {
                                    "artist": movie_name,
                                    "date": formatted_date,
                                    "time": time_formatted,
                                    "ticket_link": ticket_link,
                                }
                                results.append(movie_show)
                                
            except Exception as e:
                logging.error(f"Error processing schedule: {e}")
                continue
                
        logging.info(f"Found {len(results)} showtimes at IFC Center")
        return results

    except requests.RequestException as e:
        logging.error(f"Error fetching IFC Center website: {e}")
        return []
    except Exception as e:
        logging.error(f"Error scraping IFC Center: {e}")
        return []

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Test the scraper
    showtimes = scrape_ifc()
    for show in showtimes:
        print(show) 