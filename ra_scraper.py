import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def scrape_ra(url):
    """Scrape event data from RA"""
    try:
        # Add headers to look more like a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://ra.co',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate', 
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }

        # First make a GET request to get any required cookies
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        
        # Extract venue ID from URL
        venue_id = url.split('/')[-1]
        
        # Make API request to get events data
        api_url = f'https://ra.co/graphql'
        query = """
        query VenueEvents($id: ID!) {
            venue(id: $id) {
                events(limit: 50) {
                    title
                    date
                    startTime
                    contentUrl
                    artists {
                        name
                    }
                }
            }
        }
        """
        
        variables = {
            'id': venue_id
        }
        
        json_response = session.post(api_url, 
            json={'query': query, 'variables': variables},
            headers=headers
        ).json()
        
        events = []
        if 'data' in json_response and json_response['data']['venue']:
            venue_data = json_response['data']['venue']
            for event in venue_data['events']:
                events.append({
                    'title': event['title'],
                    'date': event['date'],
                    'time': event['startTime'],
                    'url': f"https://ra.co{event['contentUrl']}",
                    'artists': [a['name'] for a in event['artists']]
                })
                
        return events

    except Exception as e:
        logging.error(f"Error scraping RA: {e}")
        return [] 