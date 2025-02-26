import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.proxy import Proxy, ProxyType
import logging
import random
import time
import os
from fake_useragent import UserAgent

logger = logging.getLogger('concert_app')

# Default free proxies - updated regularly but may be unreliable
DEFAULT_PROXIES = [
    # HTTPS proxies that can be rotated - UPDATE THESE PERIODICALLY
    '142.54.161.98:3128',
    '198.59.191.234:8080',
    '45.32.150.115:3128',
    '47.88.3.19:8080',
    '198.199.86.11:8080',
    '34.82.224.175:33333',
    '157.245.27.9:3128',
    '51.159.115.233:3128',
    '144.76.42.215:8118',
    '178.62.193.217:3128'
]

# Try to get proxies from environment variable
def get_proxies():
    """Get proxies from environment variable or use defaults"""
    env_proxies = os.environ.get('RA_PROXIES')
    if env_proxies:
        # Expected format: "ip1:port1,ip2:port2,ip3:port3"
        return env_proxies.split(',')
    return DEFAULT_PROXIES

def update_event_cache(url, events):
    """Save successful event data to cache for fallback"""
    if not events:
        return
        
    try:
        cache_file = 'ra_cache.json'
        venue_id = url.split('/')[-1]
        
        # Load existing cache or create new one
        cached_data = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
            except json.JSONDecodeError:
                # File exists but is invalid JSON, start fresh
                cached_data = {}
        
        # Update cache with new data
        cached_data[venue_id] = events
        
        # Save updated cache
        with open(cache_file, 'w') as f:
            json.dump(cached_data, f)
            
        logger.info(f"Updated cache for venue ID {venue_id} with {len(events)} events")
    except Exception as e:
        logger.error(f"Error updating cache: {e}")

def scrape_ra(url, max_retries=5):
    """Scrape event data from RA using their Next.js data with proxies and anti-blocking measures"""
    # Try to use fake_useragent for even better randomization
    try:
        ua = UserAgent()
        # Generate a list of user agents with fake_useragent
        user_agents = [ua.random for _ in range(10)]
    except Exception as e:
        logger.warning(f"Could not use fake_useragent: {e}. Using fallback user agents.")
        # Fallback user agents if fake_useragent fails
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1',
        ]
    
    # Get available proxies
    proxies = get_proxies()
    if not proxies:
        logger.warning("No proxies available, will attempt without proxy")
    else:
        logger.info(f"Using {len(proxies)} proxies for rotation")
        # Shuffle proxies
        random.shuffle(proxies)
    
    # Track which proxies have been tried and failed
    failed_proxies = set()
    
    for attempt in range(max_retries):
        current_proxy = None
        try:
            logger.info(f"Scraping RA: {url} (Attempt {attempt + 1}/{max_retries})")
            
            # Much longer initial delay between attempts
            base_delay = 60 + (attempt * 30)  # Starts at 60s, increases by 30s each attempt
            jitter = random.uniform(-10, 20)  # Add randomness
            delay = base_delay + jitter
            logger.info(f"Waiting {delay:.1f} seconds before scraping attempt {attempt + 1}...")
            time.sleep(delay)
            
            # Setup Firefox options
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            firefox_options.set_preference('javascript.enabled', True)
            
            # Extensive browser fingerprint spoofing
            firefox_options.set_preference('dom.webdriver.enabled', False)
            firefox_options.set_preference('useAutomationExtension', False)
            firefox_options.set_preference('privacy.trackingprotection.enabled', False)
            firefox_options.set_preference('network.http.referer.spoofSource', True)
            firefox_options.set_preference('network.http.sendRefererHeader', 2)
            firefox_options.set_preference('media.navigator.enabled', False)
            firefox_options.set_preference('media.peerconnection.enabled', False)
            firefox_options.set_preference('webgl.disabled', True)
            firefox_options.set_preference('browser.cache.disk.enable', False)
            firefox_options.set_preference('browser.cache.memory.enable', False)
            firefox_options.set_preference('browser.privatebrowsing.autostart', True)
            
            # Choose random User-Agent
            current_agent = random.choice(user_agents)
            firefox_options.set_preference('general.useragent.override', current_agent)
            logger.info(f"Using user agent: {current_agent}")
            
            # Set up proxy if available
            proxy = None
            if proxies and len(proxies) > len(failed_proxies):
                # Use proxy that hasn't failed yet
                available_proxies = [p for p in proxies if p not in failed_proxies]
                if available_proxies:
                    current_proxy = random.choice(available_proxies)
                    logger.info(f"Using proxy: {current_proxy}")
                    
                    # Set proxy for Firefox
                    firefox_options.set_preference("network.proxy.type", 1)
                    host, port = current_proxy.split(':')
                    firefox_options.set_preference("network.proxy.http", host)
                    firefox_options.set_preference("network.proxy.http_port", int(port))
                    firefox_options.set_preference("network.proxy.ssl", host)
                    firefox_options.set_preference("network.proxy.ssl_port", int(port))
                    # No proxy for localhost
                    firefox_options.set_preference("network.proxy.no_proxies_on", "localhost,127.0.0.1")
            
            # Create driver
            logger.info("Initializing Firefox driver...")
            driver = webdriver.Firefox(options=firefox_options)
            
            # Set a larger window size for more consistent rendering
            driver.set_window_size(1366, 768)
            
            # Set a page load timeout
            driver.set_page_load_timeout(60)
            
            try:
                # First visit several unrelated sites to build history and cookies
                sites = ['https://www.google.com', 'https://www.wikipedia.org', 'https://www.github.com']
                random.shuffle(sites)
                for site in sites[:2]:  # Just visit 2 random ones
                    try:
                        logger.info(f"Visiting {site} to build history...")
                        driver.get(site)
                        time.sleep(random.uniform(3, 7))
                    except Exception as e:
                        logger.warning(f"Could not visit {site}: {e}")
                
                # Visit RA homepage with more realistic browsing
                logger.info("Visiting RA homepage...")
                driver.get('https://ra.co')
                time.sleep(random.uniform(5, 10))
                
                # Simulate some random scrolling
                for _ in range(3):
                    scroll_amount = random.uniform(100, 500)
                    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(1, 3))
                
                # Wait a bit before going to target URL
                time.sleep(random.uniform(5, 10))
                
                # Then visit the venue page
                logger.info(f"Navigating to target URL: {url}")
                driver.get(url)
                
                # Longer wait for initial load
                time.sleep(random.uniform(10, 15))
                
                # Simulate more realistic user browsing behavior
                scroll_positions = [0.2, 0.4, 0.6, 0.8, 1.0]
                random.shuffle(scroll_positions)
                
                for pos in scroll_positions:
                    # Scroll to percentage of page height
                    driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {pos});")
                    time.sleep(random.uniform(2, 5))
                    
                    # Sometimes move mouse (via JavaScript)
                    if random.random() > 0.5:
                        x, y = random.randint(100, 1000), random.randint(100, 600)
                        driver.execute_script(f"document.elementFromPoint({x}, {y}).dispatchEvent(new MouseEvent('mouseover'));")
                
                # Final wait to ensure everything is loaded
                time.sleep(random.uniform(8, 15))
                
                # Get page source
                html = driver.page_source
                
                # Check if we got blocked
                if "Access denied" in html or "Too many requests" in html or "Cloudflare" in html:
                    if current_proxy:
                        logger.warning(f"Proxy {current_proxy} was blocked. Marking as failed.")
                        failed_proxies.add(current_proxy)
                    logger.warning(f"Detected blocking on attempt {attempt + 1}, trying different configuration...")
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
                # Update cache with successful results
                update_event_cache(url, events)
                return events
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            
            # If we've reached the last retry, try cloudscraper as a last resort
            if attempt == max_retries - 1:
                logger.warning("All Selenium attempts failed, trying cloudscraper as last resort")
                try:
                    # Import here to avoid issues if it's not installed
                    import cloudscraper
                    
                    # Create a cloudscraper session
                    scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': 'firefox',
                            'platform': 'windows',
                            'mobile': False
                        },
                        delay=20
                    )
                    
                    # Set random user agent
                    headers = {'User-Agent': random.choice(user_agents)}
                    
                    # Try to get the page
                    logger.info(f"Using cloudscraper for final attempt on {url}")
                    
                    # First visit RA homepage
                    scraper.get('https://ra.co')
                    time.sleep(random.uniform(5, 10))
                    
                    # Then the target URL
                    response = scraper.get(url, headers=headers)
                    
                    # Check if successful
                    if response.status_code == 200:
                        html = response.text
                        
                        # Check if we got blocked
                        if "Access denied" not in html and "Too many requests" not in html and "Cloudflare" not in html:
                            # Parse HTML
                            soup = BeautifulSoup(html, "html.parser")
                            
                            # Extract the __NEXT_DATA__ JSON
                            next_data_script = soup.find("script", id="__NEXT_DATA__")
                            if next_data_script:
                                data = json.loads(next_data_script.string)
                                
                                # Get the Apollo state that holds all our cached objects
                                apollo_state = data["props"]["apolloState"]
                                
                                events = []
                                
                                # Process events as in the main function...
                                for key, value in apollo_state.items():
                                    if key.startswith("Event:") and value.get("__typename") == "Event":
                                        event = value
                                        
                                        # Process event data identically to the main method
                                        event_date = event.get("date", "")[:10]
                                        
                                        start_time_iso = event.get("startTime", "")
                                        time_formatted = ""
                                        if start_time_iso:
                                            try:
                                                dt = datetime.fromisoformat(start_time_iso)
                                                time_formatted = dt.strftime("%H:%M")
                                            except Exception as e:
                                                time_formatted = start_time_iso[11:16]
                                        
                                        artist_names = []
                                        for artist_ref in event.get("artists", []):
                                            ref_key = artist_ref.get("__ref")
                                            if ref_key and ref_key in apollo_state:
                                                artist_obj = apollo_state[ref_key]
                                                name = artist_obj.get("name")
                                                if name:
                                                    artist_names.append(name)
                                        artist_str = ", ".join(artist_names)
                                        
                                        venue_name = ""
                                        venue_address = ""
                                        venue_ref = event.get("venue", {}).get("__ref")
                                        if venue_ref and venue_ref in apollo_state:
                                            venue_obj = apollo_state[venue_ref]
                                            venue_name = venue_obj.get("name", "")
                                            venue_address = venue_obj.get("address", "")
                                        
                                        content_url = event.get("contentUrl", "")
                                        ticket_link = "https://ra.co" + content_url
                                        
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
                                
                                if events:
                                    logger.info(f"Successfully scraped {len(events)} events with cloudscraper!")
                                    # Update cache with successful results
                                    update_event_cache(url, events)
                                    return events
                                
                except Exception as cloud_error:
                    logger.error(f"Cloudscraper attempt also failed: {cloud_error}")
                    
    # Last resort: try to get data from cached venues file
    try:
        cache_file = 'ra_cache.json'
        logger.warning(f"All methods failed, checking for cache file {cache_file}")
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                venue_id = url.split('/')[-1]
                if venue_id in cached_data:
                    logger.info(f"Using cached data for venue ID {venue_id}")
                    return cached_data[venue_id]
    except Exception as cache_error:
        logger.error(f"Could not use cache: {cache_error}")
        
    return []  # Return empty list if all retries failed