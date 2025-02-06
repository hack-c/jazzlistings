import openai
from config import OPENAI_API_KEY
import json
from openai import OpenAI

openai.api_key = OPENAI_API_KEY
client = OpenAI()

def parse_markdown(markdown_content):
    """
    Parse the markdown content to extract concert information using OpenAI GPT-4o.

    Parameters:
        markdown_content (str): The markdown content to parse.

    Returns:
        list: A list of dictionaries containing concert information, or None if parsing fails.
    """
    # Prepare the prompt for OpenAI
    prompt = f"""
    You are an assistant that extracts concert information from the following markdown content and provides it in JSON format.
    Focus on finding concert details like dates, times, artists, and venue information.

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
            "price_range": "$XX - $YY",
            "special_notes": "Any special notes"
        }},
        ...
    ]

    Important formatting rules:
    - For date, use YYYY-MM-DD format
    - For times, use 24-hour HH:MM format (e.g. "19:30" for 7:30 PM)
    - If a time is not specified or unclear, provide an empty array for times: []
    - If any other field is missing or unclear, use null
    - Assume all times are Eastern Time
    
    Provide only the JSON array as the output.
    """

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",  # Fixed typo in model name
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
