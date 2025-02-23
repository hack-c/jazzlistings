import openai
from config import OPENAI_API_KEY
import json
from openai import OpenAI
import re
from datetime import datetime, timedelta
import logging

openai.api_key = OPENAI_API_KEY
client = OpenAI()

logger = logging.getLogger('concert_app')

class Parser:
    def parse(self, content):
        logger.info("Starting content parse")
        # Replace print statements with logger
        # Only log important parsing events and errors

def parse_markdown(markdown_content, venue_info):
    """Parse markdown content into structured concert data."""
    concerts = []
    current_concert = None
    
    # Get default show times for this venue
    default_times = venue_info.get('default_times', ['8:00 PM'])  # Fallback to 8 PM if not specified
    
    # Split content into lines for processing
    lines = markdown_content.split('\n')
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        # Check for date patterns
        date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s*(?:‑|-|–)\s*(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+)?\d{1,2}', line)
        if date_match:
            if current_concert:
                concerts.append(current_concert)
            
            date_str = date_match.group(0)
            start_date, end_date = parse_date_range(date_str)
            
            current_concert = {
                'dates': [start_date],  # We'll expand this for each date in the range
                'artists': [],
                'times': default_times.copy(),  # Use venue's default times
                'ticket_link': None,
                'price_range': None,
                'special_notes': []
            }
            
            # Create a concert entry for each date in the range
            current_date = start_date
            while current_date <= end_date:
                concerts.append({
                    'dates': [current_date],
                    'artists': current_concert['artists'].copy(),
                    'times': current_concert['times'],
                    'ticket_link': current_concert['ticket_link'],
                    'price_range': current_concert['price_range'],
                    'special_notes': current_concert['special_notes'].copy()
                })
                current_date += timedelta(days=1)
            
            continue
            
        # Check for artist names (lines starting with ** or after ### that aren't dates)
        if '**' in line or (line.startswith('###') and not re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)', line)):
            artist_name = re.sub(r'[*#\s–-]', '', line).strip()
            if artist_name and current_concert:
                current_concert['artists'].append(artist_name)
                
        # Check for ticket links
        if '[TICKETS]' in line:
            ticket_match = re.search(r'\((.*?)\)', line)
            if ticket_match and current_concert:
                current_concert['ticket_link'] = ticket_match.group(1)
                
        # Check for special notes (lines starting with >)
        if line.startswith('>'):
            if current_concert:
                current_concert['special_notes'].append(line.strip('> '))

    # Add the last concert if exists
    if current_concert:
        concerts.append(current_concert)
        
    return concerts

def parse_date_range(date_str):
    """Parse a date range string into start and end dates."""
    parts = re.split(r'\s*(?:‑|-|–)\s*', date_str)
    
    if len(parts) == 2:
        # Handle case where month is only mentioned once (e.g., "February 11 - 16")
        if not any(month in parts[1] for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
            month = re.findall(r'(January|February|March|April|May|June|July|August|September|October|November|December)', parts[0])[0]
            parts[1] = f"{month} {parts[1]}"
    
    start_date = parse_date(parts[0].strip())
    end_date = parse_date(parts[1].strip())
    
    return start_date, end_date

def parse_date(date_str):
    """Parse a date string into a date object."""
    # Add current year if not present
    if not re.search(r'\d{4}', date_str):
        date_str = f"{date_str}, {datetime.now().year}"
    
    try:
        return datetime.strptime(date_str, '%B %d, %Y').date()
    except ValueError:
        try:
            return datetime.strptime(date_str, '%B %d %Y').date()
        except ValueError:
            print(f"Could not parse date: {date_str}")
            return None

def parse_markdown_old(markdown_content):
    """
    Parse markdown content to extract concert information using OpenAI GPT-4o.
    """
    prompt = f"""
    You are an assistant that extracts concert information from the following markdown content and provides it in JSON format.
    Focus on finding concert details like dates, times, artists, and venue information.

    IMPORTANT PARSING RULES:
    1. Extract ALL concerts, including those listed under "COMING SOON!"
    2. For date ranges like "February 18 - February 23", create an entry for each day in the range
    3. For listings without explicit times, use empty array for times
    4. For "COMING SOON!" listings, include them with their dates and artists
    5. Include any band member details in the special_notes field
    6. For recurring events (like "Every Monday Night"), create an entry with special handling
    7. If the artist is listed as "TBA", "TBD", or "To Be Announced", skip it

    Markdown Content:
    {markdown_content[:640000]}

    Extract the concert information and output it in the following JSON format:
    [
        {{
            "artist": "Artist Name",
            "date": "YYYY-MM-DD",
            "times": ["HH:MM"],
            "venue": "Venue Name",
            "address": "Venue Address",
            "ticket_link": "URL",
            "price_range": null,
            "special_notes": "Band members: Person1 (instrument), Person2 (instrument), ..."
        }},
        ...
    ]

    Important formatting rules:
    - For date, use YYYY-MM-DD format
    - For times, use 24-hour HH:MM format (e.g. "19:30" for 7:30 PM)
    - If a time is not specified or unclear, provide an empty array for times: []
    - If any other field is missing or unclear, use null
    - Assume all times are Eastern Time
    - Include ALL band member details in special_notes
    
    Provide only the JSON array as the output.
    """

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fixed typo in model name
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16000,
            temperature=0.2,
        )

        # Get the assistant's response
        content = response.choices[0].message.content.strip()

        # Ensure only JSON array is present
        json_start = content.find('[')
        json_end = content.rfind(']')
        if json_start != -1 and json_end != -1:
            json_content = content[json_start : json_end + 1]
            # Parse the JSON content
            data = json.loads(json_content)
            return data
        else:
            print("Failed to locate JSON array in the response.")
            return None

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        return None
