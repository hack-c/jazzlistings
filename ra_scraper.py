import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import logging
import random
import time

logger = logging.getLogger('concert_app')

def scrape_ra(url, max_retries=3):
    """Scrape event data from RA using their Next.js data"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) Firefox/123.0',
        'Mozilla/5.0 (X11; Linux x86_64) Firefox/123.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) Firefox/122.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 Firefox/123.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Firefox/122.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0'
    ]
    
    # Shuffle user agents to randomize first attempt
    random.shuffle(user_agents)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Scraping RA: {url} (Attempt {attempt + 1}/{max_retries})")
            
            # Random delay between attempts, longer for subsequent tries
            delay = random.uniform(10 + attempt * 10, 30 + attempt * 15)
            logger.info(f"Waiting {delay:.1f} seconds before scraping...")
            time.sleep(delay)
            
            # Set up Firefox with current user agent
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            firefox_options.set_preference('javascript.enabled', True)
            
            # Use next user agent from shuffled list
            current_agent = user_agents[attempt % len(user_agents)]
            firefox_options.set_preference('general.useragent.override', current_agent)
            logger.info(f"Using user agent: {current_agent}")
            
            # Fetch the page
            logger.info("Fetching page with Firefox...")
            driver = webdriver.Firefox(options=firefox_options)
            
            try:
                driver.get(url)
                
                # Random wait between 5-15 seconds for dynamic content
                wait_time = random.uniform(5, 15)
                logger.info(f"Waiting {wait_time:.1f} seconds for content to load...")
                time.sleep(wait_time)
                
                html = driver.page_source
                
                # Check if we got blocked
                if "Access denied" in html or "Too many requests" in html:
                    logger.warning(f"Detected blocking on attempt {attempt + 1}, trying different user agent...")
                    continue
                
                # Parse HTML
                soup = BeautifulSoup(html, "html.parser")
                
                # Extract the __NEXT_DATA__ JSON
                next_data_script = soup.find("script", id="__NEXT_DATA__")
                if not next_data_script:
                    logger.warning(f"Could not find __NEXT_DATA__ script on attempt {attempt + 1}, trying again...")
                    continue
                    
                data = json.loads(next_data_script.string)
                
                # Get the Apollo state that holds all our cached objects
                apollo_state = data["props"]["apolloState"]
                
                events = []
                
                for key, value in apollo_state.items():
                    # Process only objects that are events
                    if key.startswith("Event:") and value.get("__typename") == "Event":
                        event = value
                        
                        # Format date (YYYY-MM-DD)
                        event_date = event.get("date", "")[:10]
                        
                        # Extract and format the start time to "HH:MM"
                        start_time_iso = event.get("startTime", "")
                        time_formatted = ""
                        if start_time_iso:
                            try:
                                dt = datetime.fromisoformat(start_time_iso)
                                time_formatted = dt.strftime("%H:%M")
                            except Exception as e:
                                logger.warning(f"Error parsing time {start_time_iso}: {e}")
                                time_formatted = start_time_iso[11:16]
                        
                        # Get artist names by following the __ref pointers
                        artist_names = []
                        for artist_ref in event.get("artists", []):
                            ref_key = artist_ref.get("__ref")
                            if ref_key and ref_key in apollo_state:
                                artist_obj = apollo_state[ref_key]
                                name = artist_obj.get("name")
                                if name:
                                    artist_names.append(name)
                        artist_str = ", ".join(artist_names)
                        
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
                        
                        # Build the event dict
                        event_dict = {
                            "artist": artist_str,
                            "date": event_date,
                            "times": [time_formatted] if time_formatted else [],
                            "venue": venue_name,
                            "address": venue_address,
                            "ticket_link": ticket_link,
                            "price_range": None,
                            "special_notes": ""
                        }
                        events.append(event_dict)
                        logger.debug(f"Extracted event: {event_dict}")
                
                logger.info(f"Successfully scraped {len(events)} events on attempt {attempt + 1}")
                return events
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                logger.exception("All retry attempts failed")
            
    return []  # Return empty list if all retries failed 