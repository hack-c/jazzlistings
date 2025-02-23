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
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import html2text
from pdfminer.high_level import extract_text
import logging

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
        options = Options()
        options.add_argument('--headless')
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        
        # Add Firefox-specific options
        options.set_preference('browser.download.folderList', 2)
        options.set_preference('browser.download.manager.showWhenStarting', False)
        # Suppress geckodriver version warnings
        options.set_preference('log.level', 'ERROR')

        try:
            # Use Service class to configure geckodriver
            from selenium.webdriver.firefox.service import Service
            service = Service(log_path=os.devnull)  # Suppress geckodriver logs
            driver = webdriver.Firefox(options=options, service=service)
            
            driver.get(url)
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            html_content = driver.page_source
            return html_content
        except Exception as e:
            logger.error(f"Selenium error: {e}")
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
        """Fetch the given URL and return the Markdown content."""
        cache_file = self.get_cache_filename(url)
        
        # Try Firecrawl first
        try:
            logger.info("Attempting Firecrawl scrape")
            scrape_result = self.app.scrape_url(url, params={'formats': ['markdown']})
            time.sleep(6)
            if 'markdown' in scrape_result:
                return scrape_result['markdown']
        except Exception as e:
            if "Insufficient credits" in str(e):
                logger.info("Firecrawl credits exhausted, falling back to direct scraping")
            else:
                logger.warning(f"Firecrawl error: {e}")

        # Check cache
        if self.is_cache_valid(cache_file):
            logger.info("Using cached content")
            cached_content = self.load_cache(cache_file)
            if url.lower().endswith(".pdf"):
                return self.extract_text_from_pdf(cached_content)
            return self.convert_html_to_markdown(cached_content.decode("utf-8", errors="replace"))

        # Fetch content based on type
        if url.lower().endswith(".pdf"):
            pdf_bytes, _ = self.fetch_with_requests(url)
            text = self.extract_text_from_pdf(pdf_bytes)
            self.save_cache(cache_file, pdf_bytes)
            return text
        else:
            try:
                html_content = self.fetch_with_selenium(url)
            except Exception as e:
                logger.warning(f"Selenium failed, trying Requests: {e}")
                html_bytes, _ = self.fetch_with_requests(url)
                html_content = html_bytes.decode("utf-8", errors="replace")
            
            self.save_cache(cache_file, html_content.encode("utf-8"))
            return self.convert_html_to_markdown(html_content)
