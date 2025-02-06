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
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                # Add a small delay to be respectful to servers
                sleep(0.1)
                
                # Fetch the website content
                response = self.session.get(
                    url, 
                    timeout=30,
                    verify=True,  # Enforce SSL verification
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Connection': 'keep-alive',
                    }
                )
                response.raise_for_status()
                
                return response.text
                
            except requests.exceptions.SSLError:
                # Try again without SSL verification as fallback
                try:
                    response = self.session.get(url, timeout=30, verify=False)
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    print(f"Error on SSL fallback for {url}: {e}")
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                continue
                
        print(f"All attempts failed for {url}")
        return None
