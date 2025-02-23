#!/usr/bin/env python3
from firecrawl import FirecrawlApp
from config import FIRECRAWL_API_KEY
import os
import sys
import time
import hashlib
import requests
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import html2text
from pdfminer.high_level import extract_text
import logging
from datetime import datetime
import json

logger = logging.getLogger('concert_app')

class Crawler:
    """
    Crawler class to fetch website HTML content.
    """

    def __init__(self):
        # Set up a session with common headers
        # self.session = requests.Session()
        # self.session.headers.update({
        #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        # })
        self.app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.body_width = 0

    def get_cache_filename(self, url):
        """Get the cache filename for a URL."""
        hashed = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed}.cache")

    def is_cache_valid(self, cache_file, max_age=86400):
        """Check if cache file is valid and not expired."""
        if not os.path.exists(cache_file):
            return False
        mtime = os.path.getmtime(cache_file)
        return (time.time() - mtime) < max_age

    def save_cache(self, cache_file, content):
        """Save content to cache file."""
        with open(cache_file, "wb") as f:
            f.write(content)

    def load_cache(self, cache_file):
        """Load content from cache file."""
        with open(cache_file, "rb") as f:
            return f.read()

    def fetch_with_selenium(self, url, proxy=None):
        """Uses Selenium with Firefox in headless mode."""
        options = FirefoxOptions()
        options.add_argument('--headless')
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        
        # Add Firefox-specific options
        options.set_preference('browser.download.folderList', 2)
        options.set_preference('browser.download.manager.showWhenStarting', False)
        options.set_preference('log.level', 'ERROR')

        try:
            from selenium.webdriver.firefox.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            
            service = Service(log_path=os.devnull)
            driver = webdriver.Firefox(options=options, service=service)
            
            logger.info(f"Fetching URL with Selenium: {url}")
            driver.get(url)
            
            # Wait for body to be present
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for page load
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait additional time for dynamic content   time.sleep(5)
            
            # Get the page source
            html_content = driver.page_source
            
            # Log details about the content
            content_length = len(html_content) if html_content else 0
            logger.info(f"Received {content_length} bytes of HTML from {url}")
            
            if content_length < 100:  # Arbitrary small size check
                logger.warning(f"Suspiciously small content size ({content_length} bytes) from {url}")
                return None
                
            # Log a snippet for debugging
            if html_content:
                preview = html_content[:200].replace('\n', ' ')
                logger.debug(f"Content preview: {preview}...")
            
            return html_content
        except Exception as e:
            logger.error(f"Selenium error for {url}: {e}")
            raise
        finally:
            try:
                if 'driver' in locals():
                    driver.quit()
            except:
                pass

    def fetch_with_requests(self, url, proxy=None):
        """Uses Requests to get the raw content."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/91.0'
        }
        proxies = {"http": proxy, "https": proxy} if proxy else None
        response = requests.get(url, headers=headers, proxies=proxies, timeout=60)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type", "")

    def extract_text_from_pdf(self, pdf_bytes):
        """Extract text from PDF bytes."""
        pdf_io = BytesIO(pdf_bytes)
        return extract_text(pdf_io)

    def convert_html_to_markdown(self, html_content):
        """Convert HTML to Markdown."""
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        return h.handle(html_content)

    def scrape_venue(self, url):
        """Scrape a venue's website for concert information"""
        try:
            # First try Firecrawl
            logger.info("Attempting Firecrawl scrape")
            try:
                result = self.app.scrape_url(url, params={'formats': ['markdown']})
                markdown = result['data']['markdown']
                if markdown and len(markdown.strip()) > 1:
                    return markdown
            except Exception as e:
                if "insufficient credits" in str(e).lower():
                    logger.info("Firecrawl credits exhausted, falling back to direct scraping")
                else:
                    logger.error(f"Firecrawl error: {e}")
            
            # Try Firefox first
            logger.info("Trying Firefox...")
            markdown = self.scrape_with_firefox(url)
            if markdown and len(markdown.strip()) > 1:
                return markdown
            
            # If Firefox fails or returns empty content, try Chrome
            logger.info("Firefox failed or returned empty content, trying Chrome...")
            return self.scrape_with_chrome(url)
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def scrape_with_firefox(self, url):
        """Use Firefox to fetch the page"""
        logger.info(f"Fetching URL with Firefox: {url}")
        
        options = FirefoxOptions()
        options.add_argument('--headless')
        options.set_preference('javascript.enabled', True)
        options.set_preference('dom.webdriver.enabled', False)
        
        try:
            from selenium.webdriver.firefox.service import Service
            
            service = Service(log_path=os.devnull)
            driver = webdriver.Firefox(options=options, service=service)
            
            driver.get(url)
            
            # Wait for page load
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            html_content = driver.page_source
            
            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.body_width = 0
            markdown = h.handle(html_content)
            
            logger.info(f"Firefox generated {len(markdown)} bytes of markdown")
            return markdown
            
        except Exception as e:
            logger.error(f"Firefox scraping error: {e}")
            return None
        finally:
            try:
                driver.quit()
            except:
                pass

    def scrape_with_chrome(self, url):
        """Use Chrome to fetch the page"""
        logger.info(f"Fetching URL with Chrome: {url}")
        
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--start-maximized')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Add experimental options
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            
            # Wait for page load
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait for RA.co specific elements
            if 'ra.co' in url:
                time.sleep(5)  # Give dynamic content time to load
                try:
                    # Log the page title
                    logger.info(f"Page title: {driver.title}")
                    
                    # Log any error messages that might be present
                    error_elements = driver.find_elements_by_css_selector('.error-message, .error')
                    if error_elements:
                        for elem in error_elements:
                            logger.warning(f"Found error element: {elem.text}")
                except Exception as e:
                    logger.warning(f"Error checking page elements: {e}")
            
            html_content = driver.page_source
            
            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.body_width = 0
            markdown = h.handle(html_content)
            
            # Log content details
            logger.info(f"Chrome generated {len(markdown)} bytes of markdown")
            logger.debug(f"Markdown preview: {markdown[:500]}")  # Log first 500 chars
            
            return markdown
            
        except Exception as e:
            logger.error(f"Chrome scraping error: {e}")
            return None
        finally:
            try:
                driver.quit()
            except:
                pass
