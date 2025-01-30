import openai
from config import OPENAI_API_KEY
import json
from openai import OpenAI

openai.api_key = OPENAI_API_KEY
client = OpenAI()


def parse_markdown(markdown_content):
    """
    Parse the markdown content to extract concert information using OpenAI GPT-3.5 Turbo.

    Parameters:
        markdown_content (str): The markdown content to parse.

    Returns:
        list: A list of dictionaries containing concert information, or None if parsing fails.
    """
    # Prepare the enhanced prompt for OpenAI
    prompt = f"""
    You are an assistant that extracts concert information from the following markdown content and provides it in JSON format.

    Markdown Content:
    {markdown_content}

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

    Ensure that each concert entry includes both "date" and "time". If the time is not specified, set it to null. Assume all times given are Eastern Time. 

    If any other field is missing, use null.

    Provide only the JSON array as the output.
    """

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
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
