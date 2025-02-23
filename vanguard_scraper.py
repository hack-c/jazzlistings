import re
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
import calendar
import requests


# --- Helper functions ---

def parse_date_range(date_range_str, default_year):
    """
    Given a date range string like 'February 11 – February 16' or 'February 25 - March 2',
    return (start_date, end_date) as datetime objects.
    If the end part omits the month, assume the same month as start_date.
    """
    # Normalize various dash characters to a standard hyphen
    norm = date_range_str.replace("–", "-").replace("—", "-").strip()
    parts = norm.split("-")
    if len(parts) == 1:
        start_str = parts[0].strip()
        end_str = start_str
    else:
        start_str = parts[0].strip()
        end_str = parts[1].strip()
    
    try:
        start_date = dateparser.parse(f"{start_str} {default_year}")
    except Exception:
        start_date = None

    # If the end_str contains a month name (alphabetic characters) then parse directly;
    # otherwise, assume the same month as the start_date.
    if re.search(r"[A-Za-z]", end_str):
        try:
            end_date = dateparser.parse(f"{end_str} {default_year}")
        except Exception:
            end_date = None
    else:
        try:
            month = start_date.strftime("%B")
            end_date = dateparser.parse(f"{month} {end_str} {default_year}")
        except Exception:
            end_date = None

    return start_date, end_date

def daterange(start_date, end_date):
    """Yield each date from start_date to end_date inclusive."""
    for n in range((end_date - start_date).days + 1):
        yield start_date + timedelta(n)

# --- Main scraper function ---

def scrape_events(html):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # Use current year as default
    default_year = str(datetime.now().year)
    
    # Optionally try to get year from ticket links, fallback to current year
    ticket_link = soup.find("a", class_="btn btn-primary")
    if ticket_link:
        m = re.search(r"(\d{4})", ticket_link.get("href", ""))
        if m:
            link_year = m.group(1)
            # Only use the year from link if it's current or next year
            if link_year in [str(datetime.now().year), str(datetime.now().year + 1)]:
                default_year = link_year
    
    # Find each event listing container
    event_listings = soup.find_all("div", class_="event-listing")
    for listing in event_listings:
        title_tag = listing.find("h2")
        if not title_tag:
            continue
        title_text = title_tag.get_text(strip=True)

        recurring_tag = listing.find("h3", class_="event-tagline")
        if recurring_tag:
            recurring_text = recurring_tag.get_text(strip=True)
            m_recurring = re.search(r"Every\s+(\w+)", recurring_text, re.IGNORECASE)
            if m_recurring:
                weekday_str = m_recurring.group(1)
                try:
                    target_weekday_index = list(calendar.day_name).index(weekday_str.capitalize())
                except ValueError:
                    target_weekday_index = None
                if target_weekday_index is not None:
                    current_date = datetime.now().date()
                    end_date = current_date + timedelta(days=60)
                    days_ahead = (target_weekday_index - current_date.weekday()) % 7
                    first_occurrence = current_date + timedelta(days=days_ahead)
                    # Gather band member info if available.
                    event_short = listing.find("div", class_="event-short-description")
                    band_members = []
                    if event_short:
                        for h4 in event_short.find_all("h4"):
                            strong = h4.find("strong")
                            if strong:
                                member_name = strong.get_text(strip=True)
                                remaining = h4.get_text().replace(member_name, "").strip()
                                remaining = re.sub(r"^[-–—\s]+", "", remaining)
                                if remaining:
                                    band_members.append(f"{member_name} ({remaining})")
                                else:
                                    band_members.append(member_name)
                    special_notes = "Band members: " + ", ".join(band_members) if band_members else ""
                    ticket_a = listing.find("a", class_="btn btn-primary")
                    ticket_href = ticket_a["href"] if ticket_a else ""
                    date_iter = first_occurrence
                    while date_iter <= end_date:
                        events.append({
                            "artist": title_text,
                            "date": date_iter.strftime("%Y-%m-%d"),
                            "times": ["8:00 PM", "10:00 PM"],
                            "venue": "Village Vanguard",
                            "address": "178 7th Avenue South, New York, NY 10014, United States",
                            "ticket_link": ticket_href,
                            "price_range": None,
                            "special_notes": special_notes
                        })
                        date_iter += timedelta(days=7)
                    continue  # Skip further processing of this listing
        
        # --- Handle "COMING SOON!" events with multiple sub-events ---
        if title_text.upper() == "COMING SOON!":
            event_short = listing.find("div", class_="event-short-description")
            if not event_short:
                continue
            # Look for all h4 tags that include a <strong> tag.
            sub_events = event_short.find_all("h4")
            for h4 in sub_events:
                strong = h4.find("strong")
                if not strong:
                    continue
                # The <strong> tag gives the sub-event artist.
                artist = strong.get_text(strip=True)
                # The remaining text (before the <strong>) is the date range.
                h4_text = h4.get_text(separator=" ", strip=True)
                date_range_text = h4_text.replace(artist, "").strip()
                if not re.search(r"\d", date_range_text):
                    continue
                start_date, end_date = parse_date_range(date_range_text, default_year)
                if not (start_date and end_date):
                    continue
                # Look for a <p> sibling after the h4 that contains band info.
                p_tag = h4.find_next_sibling("p")
                if p_tag:
                    note = p_tag.get_text(strip=True)
                    # Remove any leading 'with ' if present.
                    note = re.sub(r"^with\s+", "", note, flags=re.IGNORECASE)
                    special_notes = f"Band members: {note}"
                else:
                    special_notes = ""
                # Use the main listing ticket link
                ticket_a = listing.find("a", class_="btn btn-primary")
                ticket_href = ticket_a["href"] if ticket_a else ""
                # Expand the date range
                for single_date in daterange(start_date, end_date):
                    events.append({
                        "artist": artist,
                        "date": single_date.strftime("%Y-%m-%d"),
                        "times": ["8:00 PM", "10:00 PM"],
                        "venue": "Village Vanguard",
                        "address": "178 7th Avenue South, New York, NY 10014, United States",
                        "ticket_link": ticket_href,
                        "price_range": None,
                        "special_notes": special_notes
                    })
        else:
            # --- Handle normal events ---
            # Look for an h3 (ignoring those with the "event-tagline" class) that contains digits.
            h3_tags = listing.find_all("h3")
            date_range_text = None
            for h3 in h3_tags:
                if "event-tagline" in h3.get("class", []):
                    continue
                if re.search(r"\d", h3.get_text()):
                    date_range_text = h3.get_text(strip=True)
                    break
            if not date_range_text:
                continue
            start_date, end_date = parse_date_range(date_range_text, default_year)
            if not (start_date and end_date):
                continue
            # Look for band member info inside the event-short-description.
            event_short = listing.find("div", class_="event-short-description")
            band_members = []
            if event_short:
                for h4 in event_short.find_all("h4"):
                    strong = h4.find("strong")
                    if strong:
                        member_name = strong.get_text(strip=True)
                        # Remove the member name from the h4 text to isolate the instrument.
                        remaining = h4.get_text().replace(member_name, "").strip()
                        remaining = re.sub(r"^[-–—\s]+", "", remaining)
                        if remaining:
                            band_members.append(f"{member_name} ({remaining})")
                        else:
                            band_members.append(member_name)
            special_notes = "Band members: " + ", ".join(band_members) if band_members else ""
            ticket_a = listing.find("a", class_="btn btn-primary")
            ticket_href = ticket_a["href"] if ticket_a else ""
            
            for single_date in daterange(start_date, end_date):
                events.append({
                    "artist": title_text,
                    "date": single_date.strftime("%Y-%m-%d"),
                    "times": ["8:00 PM", "10:00 PM"],
                    "venue": "Village Vanguard",
                    "address": "178 7th Avenue South, New York, NY 10014, United States",
                    "ticket_link": ticket_href,
                    "price_range": None,
                    "special_notes": special_notes
                })
    return events

def scrape_vanguard():
    """Main scraper function to be called from outside"""
    url = "https://villagevanguard.com/"
    response = requests.get(url)
    response.raise_for_status()
    html = response.text
    return scrape_events(html)

if __name__ == "__main__":
    events = scrape_vanguard()
    print(json.dumps(events, indent=4)) 