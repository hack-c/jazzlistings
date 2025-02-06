from crawler import Crawler
from parser import parse_html
from database import Session, SessionLocal, init_db
from models import Artist, Venue, Concert, ConcertTime
from datetime import datetime, timedelta

from flask import Flask, render_template
app = Flask(__name__)

from collections import defaultdict
from sqlalchemy import select

def main():
    """
    Main function that orchestrates the crawling, parsing, and storing of concert data.
    """
    # Initialize the database
    init_db()
    session = Session()

    # List of venue websites to crawl
    venues = [
        {'name': 'Village Vanguard', 'url': 'https://villagevanguard.com/', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Smalls Jazz Club', 'url': 'https://smallslive.com/', 'default_times': ['7:30 PM', '9:00 PM', '10:30 PM']},
        {'name': 'Mezzrow Jazz Club', 'url': 'https://mezzrow.com/', 'default_times': ['7:30 PM', '9:00 PM', '10:30 PM']},
        # {'name': 'Dizzy\'s Club', 'url': 'https://jazz.org/dizzys-club/', 'default_times': ['7:30 PM', '9:30 PM']},
        # {'name': 'The Jazz Gallery', 'url': 'https://jazzgallery.org/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        # {'name': 'Blue Note', 'url': 'https://www.bluenotejazz.com/', 'default_times': ['8:00 PM', '10:30 PM']},
        # {'name': 'Ornithology Jazz Club', 'url': 'https://www.ornithologyjazzclub.com/events-2/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        # {'name': 'Ornithology Cafe', 'url': 'https://www.ornithologyjazzclub.com/new-page-1/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        # {'name': 'Bar LunÀtico', 'url': 'https://www.barlunatico.com/music/', 'default_times': ['9:00 PM', '10:15 PM']},
        # {'name': 'Bar Bayeux', 'url': 'https://www.barbayeux.com/jazz/', 'default_times': ['8:00 PM', '9:30 PM']},
        # {'name': 'Marians Jazz Room', 'url': 'https://www.mariansbrooklyn.com/events', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'The Owl Music Parlor', 'url': 'https://theowl.nyc/calendar/', 'default_times': ['8:00 PM']},
        # {'name': 'Zinc Bar', 'url': 'https://zincbar.com/', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'Mona\'s', 'url': 'https://www.monascafenyc.com/', 'default_times': ['11:00 PM']},
        # {'name': 'The Stone', 'url': 'http://thestonenyc.com/calendar.php', 'default_times': ['8:30 PM']},
        # {'name': 'Abrons Art Center', 'url': 'https://abronsartscenter.org/calendar', 'default_times': ['7:00 PM']},
        # {'name': 'Café Erzulie', 'url': 'https://www.cafeerzulie.com/events', 'default_times': ['8:00 PM']},
        # {'name': 'Nublu 151', 'url': 'https://nublu.net/program', 'default_times': ['9:00 PM', '11:00 PM']},
        # {'name': 'Umbra Café', 'url': 'https://www.umbrabrooklyn.com/events', 'default_times': ['7:00 PM']},
        # {'name': 'Arthur\'s Tavern', 'url': 'https://arthurstavern.nyc/events/', 'default_times': ['7:00 PM', '9:30 PM']},
        # {'name': 'Birdland', 'url': 'https://www.birdlandjazz.com/', 'default_times': ['5:30 PM', '7:00 PM', '9:30 PM']},
        # {'name': 'Barbès', 'url': 'https://www.barbesbrooklyn.com/events', 'default_times': ['8:00 PM', '10:00 PM']},
        # {'name': 'Smoke Jazz & Supper Club', 'url': 'https://livestreams.smokejazz.com/', 'default_times': ['7:00 PM', '9:00 PM', '10:30 PM']},
        # {'name': 'Room 623 at B2 Harlem', 'url': 'https://www.room623.com/tickets', 'default_times': ['8:00 PM', '10:00 PM']},
        # {'name': 'Soapbox Gallery', 'url': 'https://www.soapboxgallery.org/calendar', 'default_times': ['8:00 PM']},
        # {'name': 'Silvana', 'url': 'https://silvana-nyc.com/calendar.php', 'default_times': ['8:00 PM', '10:00 PM']},
        # {'name': 'Sistas\' Place', 'url': 'https://sistasplace.org/', 'default_times': ['9:00 PM']},
        # {'name': 'Drom', 'url': 'https://dromnyc.com/events/', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'Roulette', 'url': 'https://roulette.org/calendar/', 'default_times': ['8:00 PM']},
        # {'name': 'Jazzmobile', 'url': 'https://jazzmobile.org/', 'default_times': ['7:00 PM']},
        # {'name': 'The Django', 'url': 'https://www.thedjangonyc.com/events', 'default_times': ['7:30 PM', '9:30 PM']},
        # {'name': 'Pangea', 'url': 'https://www.pangeanyc.com/music/', 'default_times': ['7:00 PM']},
        # {'name': 'The Ear Inn', 'url': 'https://www.theearinn.com/music-schedule/', 'default_times': ['8:00 PM']},
        # {'name': 'Shrine', 'url': 'https://shrinenyc.com/', 'default_times': ['8:00 PM', '10:00 PM']},
        # {'name': 'Chelsea Table + Stage', 'url': 'https://www.chelseatableandstage.com/tickets-shows', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'The Keep', 'url': 'https://www.thekeepny.com/calendar', 'default_times': ['8:00 PM']},
        # {'name': 'Joe\'s Pub', 'url': 'https://publictheater.org/joes-pub/', 'default_times': ['7:00 PM', '9:30 PM']},
        # {'name': 'Klavierhaus', 'url': 'https://event.klavierhaus.com/k/calendar', 'default_times': ['7:00 PM']},
        # {'name': 'Saint Peter\'s Church', 'url': 'https://www.saintpeters.org/events', 'default_times': ['1:00 PM', '7:00 PM']},
        # {'name': 'Minton\'s Playhouse', 'url': 'https://www.eventbrite.com/o/mintons-playhouse-76715695933', 'default_times': ['7:00 PM', '9:30 PM']},
        # {'name': 'National Sawdust', 'url': 'https://www.nationalsawdust.org/performances-prev', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'The Cutting Room', 'url': 'https://thecuttingroomnyc.com/calendar/', 'default_times': ['7:00 PM', '9:30 PM']},
        # {'name': 'Swing 46', 'url': 'https://swing46.nyc/calendar/', 'default_times': ['8:30 PM', '10:30 PM']},
        # {'name': 'The Appel Room', 'url': 'https://www.lincolncenter.org/venue/the-appel-room/v/calendar', 'default_times': ['7:30 PM', '9:30 PM']},
        # {'name': 'Symphony Space', 'url': 'https://www.symphonyspace.org/events', 'default_times': ['7:00 PM', '9:00 PM']},
        # {'name': 'Le Poisson Rouge', 'url': 'https://www.lpr.com/', 'default_times': ['7:00 PM', '9:30 PM']}
        
    ]

    crawler = Crawler()

    for venue_info in venues:
        venue_name = venue_info['name']
        venue_url = venue_info['url']
        print(f"Scraping {venue_name} at {venue_url}")
        # Scrape the venue website
        html_content = crawler.scrape_venue(venue_url)
        if html_content:
            print("Parsing html content")
            # Parse the html content to extract concert data
            concert_data_list = parse_html(html_content)
            if concert_data_list:
                print("Storing concert data")
                # Store the concert data in the database
                store_concert_data(session, concert_data_list, venue_info)
            else:
                print("Failed to parse concert data")
        else:
            print("Failed to scrape markdown content")

    session.close()


# -- In store_concert_data, replace your existing block for extracting artist_name, date, times, etc.
# -- with the following safer calls to avoid .strip() on NoneTypes. We also remove .strip() for times
# -- since it's expected to be a list, not a string.

def store_concert_data(session, concert_data_list, venue_info):
    """
    Stores the concert data into the database.

    Parameters:
        session: Database session.
        concert_data_list (list): List of concert data dictionaries.
        venue_info (dict): Venue information containing name and URL.
    """
    venue_name = venue_info['name']
    for concert_data in concert_data_list:
        # Safely retrieve and strip artist/date fields if they exist
        artist_name = (concert_data.get('artist') or '').strip()
        date_str = (concert_data.get('date') or '').strip()

        if not artist_name or not date_str:
            print("Incomplete concert data (missing artist or date), skipping entry.")
            continue

        # Handle date ranges (e.g., "2024-02-18 to 2024-02-23")
        start_date = None
        end_date = None
        if ' to ' in date_str:
            try:
                start_str, end_str = date_str.split(' to ')
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                dates = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
            except ValueError as e:
                print(f"Error parsing date range {date_str}: {e}")
                continue
        else:
            try:
                dates = [datetime.strptime(date_str, '%Y-%m-%d').date()]
            except ValueError as e:
                print(f"Error parsing date {date_str}: {e}")
                continue

        # Retrieve times as a list (or default to venue's default times)
        times_list = concert_data.get('times') or []
        if not times_list:
            print(f"Time missing for concert on {date_str}. Using default times from {venue_name}.")
            times_list = venue_info.get('default_times', ["20:00"])

        # Convert times to datetime objects
        time_objects = []
        for t in times_list:
            try:
                # Try parsing 12-hour format first
                time_obj = datetime.strptime(t, '%I:%M %p').time()
            except ValueError:
                try:
                    # Try 24-hour format
                    time_obj = datetime.strptime(t, '%H:%M').time()
                except ValueError:
                    print(f"Invalid time format: {t}")
                    continue
            time_objects.append(time_obj)

        if not time_objects:
            print(f"No valid times found for concert on {date_str}")
            continue

        # Safely retrieve remaining fields
        venue_name = (concert_data.get('venue') or venue_info['name']).strip()
        address = (concert_data.get('address') or '').strip()
        ticket_link = (concert_data.get('ticket_link') or '').strip()
        price_range = (concert_data.get('price_range') or '').strip()
        special_notes = (concert_data.get('special_notes') or '').strip()

        try:
            # Get or create artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
                session.commit()

            # Get or create venue
            venue = session.query(Venue).filter_by(name=venue_name).first()
            if not venue:
                venue = Venue(
                    name=venue_name,
                    address=address,
                    website_url=venue_info['url']
                )
                session.add(venue)
                session.commit()

            # Create a concert for each date in the range
            for concert_date in dates:
                # Check for existing concert
                existing_concert = (
                    session.query(Concert)
                    .filter_by(venue_id=venue.id, date=concert_date)
                    .first()
                )

                if existing_concert and artist in existing_concert.artists:
                    continue

                # Create new concert
                concert = Concert(
                    venue_id=venue.id,
                    date=concert_date,
                    ticket_link=ticket_link,
                    price_range=price_range,
                    special_notes=special_notes,
                )
                concert.artists.append(artist)

                # Create child ConcertTime rows
                for time_obj in time_objects:
                    concert.times.append(ConcertTime(time=time_obj))

                session.add(concert)
                session.commit()

        except Exception as e:
            print(f"Error storing concert data: {e}")
            session.rollback()
            continue

@app.route('/')
def index():
    db = SessionLocal()
    try:
        # Get concerts for the next 30 days
        today = datetime.now().date()
        thirty_days = today + timedelta(days=30)
        
        # Query concerts ordered by date and filter for future dates
        stmt = select(Concert).where(
            Concert.date >= today,
            Concert.date <= thirty_days
        ).order_by(Concert.date)
        
        concerts = db.execute(stmt).scalars().all()
        
        return render_template('index.html', 
                             concerts=concerts,
                             today=today)
    finally:
        db.close()

if __name__ == '__main__':
    import sys
    if "server" in sys.argv:
        # Run the Flask dev server
        app.run(debug=True)
    else:
        # Default to running the crawler logic
        main()
