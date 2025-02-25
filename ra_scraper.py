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
        # Mobile User Agents
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.57 Mobile Safari/537.36',
        # Desktop User Agents
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    ]
    
    # Shuffle user agents
    random.shuffle(user_agents)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Scraping RA: {url} (Attempt {attempt + 1}/{max_retries})")
            
            # Much longer initial delay
            delay = random.uniform(45 + attempt * 20, 90 + attempt * 30)
            logger.info(f"Waiting {delay:.1f} seconds before scraping...")
            time.sleep(delay)
            
            # Set up Firefox with current user agent
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            firefox_options.set_preference('javascript.enabled', True)
            
            # Additional preferences to make it look more like a real browser
            firefox_options.set_preference('dom.webdriver.enabled', False)
            firefox_options.set_preference('useAutomationExtension', False)
            firefox_options.set_preference('privacy.trackingprotection.enabled', False)
            firefox_options.set_preference('network.http.referer.spoofSource', True)
            firefox_options.set_preference('network.http.sendRefererHeader', 2)
            
            # Use next user agent
            current_agent = user_agents[attempt % len(user_agents)]
            firefox_options.set_preference('general.useragent.override', current_agent)
            logger.info(f"Using user agent: {current_agent}")
            
            # Fetch the page
            logger.info("Fetching page with Firefox...")
            driver = webdriver.Firefox(options=firefox_options)
            
            try:
                # First visit the RA homepage
                logger.info("Visiting RA homepage first...")
                driver.get('https://ra.co')
                time.sleep(random.uniform(3, 7))
                
                # Then visit the venue page
                driver.get(url)
                
                # Longer wait for content
                wait_time = random.uniform(10, 20)
                logger.info(f"Waiting {wait_time:.1f} seconds for content to load...")
                time.sleep(wait_time)
                
                # Scroll the page a bit to simulate human behavior
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(2, 5))
                
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