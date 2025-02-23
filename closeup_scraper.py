from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import logging
import os

logger = logging.getLogger('concert_app')

def scrape_closeup():
    """Scrape Close Up's calendar using Selenium with Firefox"""
    logger.info("Starting CloseUp scrape")
    url = "https://www.closeupnyc.com/calendar"
    logger.info("Fetching Close Up calendar")
    
    # Set up Firefox options
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        from selenium.webdriver.firefox.service import Service
        service = Service(log_path=os.devnull)
        driver = webdriver.Firefox(options=options, service=service)
        
        logger.info(f"Loading URL: {url}")
        driver.get(url)
        
        # Wait for and switch to the Wix iframe
        event_iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.wuksD5"))
        )
        driver.switch_to.frame(event_iframe)
        logger.info("Switched to event widget iframe")
        
        # Wait for event cards
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.vp-event-card"))
        )
        event_cards = driver.find_elements(By.CSS_SELECTOR, 'div.vp-event-card')
        logger.info(f"Found {len(event_cards)} event cards")
        
        events = []
        for card in event_cards:
            try:
                ticket_link = card.find_element(By.CSS_SELECTOR, 'a.vp-event-link').get_attribute('href')
                artist = card.find_element(By.CSS_SELECTOR, 'div.vp-event-name').text
                date_str = card.find_element(By.CSS_SELECTOR, 'span.vp-date').text
                time_str = card.find_element(By.CSS_SELECTOR, 'span.vp-time').text
                
                # Convert date string to YYYY-MM-DD
                date_obj = datetime.strptime(date_str, '%a %b %d')
                date_obj = date_obj.replace(year=datetime.now().year)
                date = date_obj.strftime('%Y-%m-%d')
                
                event = {
                    "artist": artist,
                    "date": date,
                    "time": time_str,
                    "ticket_link": ticket_link,
                }
                events.append(event)
                logger.debug(f"Extracted: {artist} on {date}")
                
            except Exception as e:
                logger.error(f"Error processing event card: {e}")
                continue
        
        logger.info(f"Found {len(events)} events")
        
        return events
    except Exception as e:
        logger.error(f"Error scraping Close Up: {e}")
    finally:
        driver.quit()
        
        return [] 