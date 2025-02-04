import openai
from config import OPENAI_API_KEY
import json
from openai import OpenAI
from bs4 import BeautifulSoup

openai.api_key = OPENAI_API_KEY
client = OpenAI()


def parse_html(html_content):
    """
    Parse the HTML content to extract concert information using OpenAI GPT-4o.

    Parameters:
        html_content (str): The HTML content to parse.

    Returns:
        list: A list of dictionaries containing concert information, or None if parsing fails.
    """
    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text content
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)

    except Exception as e:
        print(f"Error preprocessing HTML: {e}")
        return None

    # Prepare the prompt for OpenAI
    prompt = f"""
    You are an assistant that extracts concert information from the following website content and provides it in JSON format.
    The content has been extracted from HTML and may contain various formatting artifacts.
    Focus on finding concert details like dates, times, artists, and venue information.

    Website Content:
    {text[:8000]}  # Limit content length to avoid token limits

    Extract the concert information and output it in the following JSON format:

    [
        {{
            "artist": "Artist Name",
            "date": "YYYY-MM-DD",
            "times": ["HH:MM", "HH:MM"],
            "venue": "Venue Name",
            "address": "Venue Address",
            "ticket_link": "URL",
            "price_range": "$XX - $YY",
            "special_notes": "Any special notes"
        }},
        ...
    ]

    Ensure that each concert entry includes both "date" and "times". If the time is not specified, set it to null.
    Assume all times given are Eastern Time. If any other field is missing, use null.
    
    Provide only the JSON array as the output.
    """

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",  # Fixed typo in model name
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
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
