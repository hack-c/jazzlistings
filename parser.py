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

def parse_markdown_regex(markdown_content, venue_info):
    """Parse markdown content into concert data using regex (fallback method)"""
    logger = logging.getLogger('concert_app')
    logger.info(f"Parsing markdown for {venue_info['name']} using regex")
    
    # Log the size of markdown content
    logger.info(f"Markdown content size: {len(markdown_content)} bytes")
    
    # Log a preview of the markdown
    preview = markdown_content[:500].replace('\n', ' ')
    logger.debug(f"Markdown preview: {preview}...")
    
    concerts = []
    current_concert = None  # Initialize current_concert
    
    try:
        # Get default show times for this venue
        default_times = venue_info.get('default_times', ['8:00 PM'])  # Fallback to 8 PM if not specified
        
        # Split content into lines for processing
        lines = markdown_content.split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Log line for debugging
            logger.debug(f"Processing line: {line}")
            
            # Check for date patterns
            date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s*(?:‑|-|–)\s*(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+)?\d{1,2}', line)
            if date_match:
                # If we have a previous concert, add it to the list
                if current_concert and current_concert.get('artists'):
                    logger.debug(f"Adding concert: {current_concert}")
                    concerts.append(current_concert)
                
                date_str = date_match.group(0)
                logger.debug(f"Found date range: {date_str}")
                start_date, end_date = parse_date_range(date_str)
                
                # Create a concert entry for each date in the range
                current_date = start_date
                while current_date <= end_date:
                    current_concert = {
                        'date': current_date.strftime('%Y-%m-%d'),
                        'artists': [],
                        'times': default_times.copy(),  # Use venue's default times
                        'ticket_link': None,
                        'price_range': None,
                        'special_notes': []
                    }
                    concerts.append(current_concert)
                    current_date += timedelta(days=1)
                
                continue
            
            # Only process other fields if we have a current concert
            if current_concert:
                # Check for artist names (lines starting with ** or after ### that aren't dates)
                if ('**' in line or line.startswith('###')) and not re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)', line):
                    artist_name = re.sub(r'[*#\s–-]', '', line).strip()
                    if artist_name:
                        logger.debug(f"Found artist: {artist_name}")
                        current_concert['artists'].append(artist_name)
                
                # Check for ticket links
                if '[TICKETS]' in line or 'Buy Tickets' in line:
                    ticket_match = re.search(r'\((.*?)\)', line)
                    if ticket_match:
                        current_concert['ticket_link'] = ticket_match.group(1)
                        logger.debug(f"Found ticket link: {current_concert['ticket_link']}")
                
                # Check for special notes (lines starting with >)
                if line.startswith('>'):
                    note = line.strip('> ')
                    current_concert['special_notes'].append(note)
                    logger.debug(f"Found special note: {note}")

        # Add the last concert if it exists and has artists
        if current_concert and current_concert.get('artists'):
            logger.debug(f"Adding final concert: {current_concert}")
            concerts.append(current_concert)
        
        # Log the results
        logger.info(f"Found {len(concerts)} concerts for {venue_info['name']}")
        if concerts:
            logger.debug(f"First concert: {concerts[0]}")
            
    except Exception as e:
        logger.error(f"Error parsing markdown for {venue_info['name']}: {e}")
        logger.exception(e)  # This will log the full traceback
        
    return concerts

def parse_markdown(markdown_content, venue_info):
    """Parse markdown content into concert data using OpenAI"""
    logger = logging.getLogger('concert_app')
    logger.info(f"Parsing markdown for {venue_info['name']} using OpenAI")
    
    try:
        # Prepare the system message
        system_msg = f"""
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

        Extract the concert information and output it in the following JSON format:
        {{
            "concerts": [
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
        }}

        Important formatting rules:
        - For date, use YYYY-MM-DD format
        - For times, use 24-hour HH:MM format (e.g. "19:30" for 7:30 PM)
        - If a time is not specified or unclear, provide an empty array for times: []
        - If any other field is missing or unclear, use null
        - Assume all times are Eastern Time
        - Include ALL band member details in special_notes
        """

        # Prepare the user message with venue context
        user_msg = f"""Parse this concert listing for {venue_info['name']}.
        Default show times are: {venue_info.get('default_times', ['8:00 PM'])}

        Content:
        {markdown_content[:640000]}"""

        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=16000,
            temperature=0,
            response_format={ "type": "json_object" }
        )

        # Parse the response
        result = json.loads(response.choices[0].message.content)
        concerts = result.get('concerts', [])  # Get the concerts array from the response
        
        logger.info(f"OpenAI parser found {len(concerts)} concerts")
        if concerts:
            logger.debug(f"First concert: {concerts[0]}")
            
        return concerts

    except Exception as e:
        logger.error(f"Error using OpenAI parser: {e}")
        logger.exception(e)  # Log the full traceback
        
        # Fallback to regex parser
        logger.info("Falling back to regex parser")
        return parse_markdown_regex(markdown_content, venue_info)

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
