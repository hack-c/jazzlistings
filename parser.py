import openai
from config import OPENAI_API_KEY
import json
from openai import OpenAI

openai.api_key = OPENAI_API_KEY
client = OpenAI()

def parse_markdown(markdown_content):
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
