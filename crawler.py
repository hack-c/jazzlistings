import requests
from time import sleep


class Crawler:
    """
    Crawler class to fetch website HTML content.
    """

    def __init__(self):
        # Set up a session with common headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def scrape_venue(self, url):
        """
        Fetch the given URL and return the HTML content.

        Parameters:
            url (str): The URL of the website to scrape.

        Returns:
            str: HTML content of the website, or None if fetching fails.
        """
        try:
            # Add a small delay to be respectful to servers
            sleep(0.5)            
            # Fetch the website content
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
