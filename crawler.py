from firecrawl import FirecrawlApp
from config import FIRECRAWL_API_KEY
import requests
from time import sleep
import os
import hashlib
import time
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
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
        hashed = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed}.cache")

    def is_cache_valid(self, cache_file, max_age=86400):
        if not os.path.exists(cache_file):
            return False
        mtime = os.path.getmtime(cache_file)
        return (time.time() - mtime) < max_age

    def save_cache(self, cache_file, content):
        with open(cache_file, "wb") as f:
            f.write(content)

    def load_cache(self, cache_file):
        with open(cache_file, "rb") as f:
            return f.read()

    def fetch_with_selenium(self, url):
        """Uses Selenium with Chrome in headless mode."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        try:
            driver = webdriver.Chrome(options=options)
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
                driver.quit()
            except:
                pass

    def fetch_with_requests(self, url):
        """Uses Requests to get the raw content."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
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
        """
        Fetch the given URL and return the Markdown content.
        First tries Firecrawl, falls back to direct scraping.
        """
        max_retries = 3
        retry_delay = 1
        
        # Try Firecrawl first
        try:
            logger.info("Attempting Firecrawl scrape")
            scrape_result = self.app.scrape_url(url, params={'formats': ['markdown']})
            sleep(6)
            if 'markdown' in scrape_result:
                return scrape_result['markdown']
        except Exception as e:
            if "Insufficient credits" in str(e):
                logger.info("Firecrawl credits exhausted, falling back to direct scraping")
            else:
                logger.warning(f"Firecrawl error: {e}")
        
        # Fallback to direct scraping
        logger.info("Using direct scraping")
        for attempt in range(max_retries):
            try:
                # Try Selenium first
                try:
                    html_content = self.fetch_with_selenium(url)
                    return self.convert_html_to_markdown(html_content)
                except Exception as e:
                    logger.warning(f"Selenium failed, trying Requests: {e}")
                    html_bytes, _ = self.fetch_with_requests(url)
                    return self.convert_html_to_markdown(html_bytes.decode("utf-8", errors="replace"))
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep(retry_delay)
                    retry_delay *= 2
        
        logger.error(f"All scraping attempts failed for {url}")
        return None

    def crawl(self):
        logger.info(f"Scraping {self.venue['name']} using {self.__class__.__name__}")
        # ... crawling code ...
        
        logger.info(f"Found {len(concerts)} concerts at {self.venue['name']}")
        for concert in concerts:
            logger.info(f"Concert: {concert['artist']} at {concert['date']} {concert['time']}")
