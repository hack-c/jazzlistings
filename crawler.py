from firecrawl import FirecrawlApp
from config import FIRECRAWL_API_KEY
from time import sleep


class Crawler:
    """
    Crawler class uses Firecrawl SDK to scrape websites and return markdown content.
    """

    def __init__(self):
        # Initialize the Firecrawl application with the API key
        self.app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    def scrape_venue(self, url):
        """
        Scrape the given URL and return the markdown content.

        Parameters:
            url (str): The URL of the website to scrape.

        Returns:
            str: Markdown content of the website, or None if scraping fails.
        """
        try:
            # Scrape the website and return the markdown content
            scrape_result = self.app.crawl_url(
                url, params={'formats': ['markdown']})
            sleep(6)
            if 'markdown' in scrape_result:
                return scrape_result['markdown']
            else:
                return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
