from crawler import Crawler
from parser import parse_markdown
from database import Session, SessionLocal, init_db
from models import Artist, Venue, Concert, ConcertTime, User
from datetime import datetime, timedelta
from time import sleep
import random
from tenacity import retry, stop_after_attempt, wait_exponential
from flask import Flask, render_template, session
from collections import defaultdict
from sqlalchemy import select
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import os
from auth import auth
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev')  # Change in production
app.register_blueprint(auth)

load_dotenv()  # Add this near the top of main.py

# Add user context processor
@app.context_processor
def inject_user():
    if 'user_id' in session:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id=session['user_id']).first()
            return {'user': user}
        finally:
            db.close()
    return {'user': None}

def process_venue(venue_info, session):
    """Process a single venue with strict rate limiting"""
    venue_name = venue_info['name']
    venue_url = venue_info['url']
    print(f"Scraping {venue_name} at {venue_url}")
    
    # Add minimum 6 second delay between requests (10 req/min)
    sleep(random.uniform(6, 8))
    
    crawler = Crawler()
    try:
        markdown_content = scrape_with_retry(crawler, venue_url, venue_name)
        if not markdown_content:
            print(f"Failed to scrape markdown content for {venue_name}")
            return
        
        print(f"Parsing markdown content for {venue_name}")
        concert_data_list = parse_markdown(markdown_content)
        if concert_data_list:
            print(f"Storing concert data for {venue_name}")
            store_concert_data(session, concert_data_list, venue_info)
        else:
            print(f"Failed to parse concert data for {venue_name}")
    except Exception as e:
        print(f"Error processing {venue_name}: {e}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=10, min=10, max=120),  # Increased delays
    reraise=True
)
def scrape_with_retry(crawler, url, venue_name):
    """Attempt to scrape with longer exponential backoff retry"""
    try:
        return crawler.scrape_venue(url)
    except Exception as e:
        if "429" in str(e):  # Rate limit error
            print(f"Rate limit hit for {venue_name}, backing off...")
            # Add longer delay on rate limit
            sleep(random.uniform(15, 20))
        raise

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
        {'name': 'Dizzy\'s Club', 'url': 'https://jazz.org/dizzys-club/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'The Jazz Gallery', 'url': 'https://jazzgallery.org/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Blue Note', 'url': 'https://www.bluenotejazz.com/', 'default_times': ['8:00 PM', '10:30 PM']},
        {'name': 'Ornithology Jazz Club', 'url': 'https://www.ornithologyjazzclub.com/events-2/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        {'name': 'Ornithology Cafe', 'url': 'https://www.ornithologyjazzclub.com/new-page-1/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        {'name': 'Bar LunÀtico', 'url': 'https://www.barlunatico.com/music/', 'default_times': ['9:00 PM', '10:15 PM']},
        {'name': 'Bar Bayeux', 'url': 'https://www.barbayeux.com/jazz/', 'default_times': ['8:00 PM', '9:30 PM']},
        {'name': 'Marians Jazz Room', 'url': 'https://www.mariansbrooklyn.com/events', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'The Owl Music Parlor', 'url': 'https://theowl.nyc/calendar/', 'default_times': ['8:00 PM']},
        {'name': 'Zinc Bar', 'url': 'https://zincbar.com/', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'Mona\'s', 'url': 'https://www.monascafenyc.com/', 'default_times': ['11:00 PM']},
        {'name': 'The Stone', 'url': 'http://thestonenyc.com/calendar.php', 'default_times': ['8:30 PM']},
        {'name': 'Abrons Art Center', 'url': 'https://abronsartscenter.org/calendar', 'default_times': ['7:00 PM']},
        {'name': 'Café Erzulie', 'url': 'https://www.cafeerzulie.com/events', 'default_times': ['8:00 PM']},
        {'name': 'Nublu 151', 'url': 'https://nublu.net/program', 'default_times': ['9:00 PM', '11:00 PM']},
        {'name': 'Umbra Café', 'url': 'https://www.umbrabrooklyn.com/events', 'default_times': ['7:00 PM']},
        {'name': 'Arthur\'s Tavern', 'url': 'https://arthurstavern.nyc/events/', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'Birdland', 'url': 'https://www.birdlandjazz.com/', 'default_times': ['5:30 PM', '7:00 PM', '9:30 PM']},
        {'name': 'Barbès', 'url': 'https://www.barbesbrooklyn.com/events', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Smoke Jazz & Supper Club', 'url': 'https://livestreams.smokejazz.com/', 'default_times': ['7:00 PM', '9:00 PM', '10:30 PM']},
        {'name': 'Room 623 at B2 Harlem', 'url': 'https://www.room623.com/tickets', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Soapbox Gallery', 'url': 'https://www.soapboxgallery.org/calendar', 'default_times': ['8:00 PM']},
        {'name': 'Silvana', 'url': 'https://silvana-nyc.com/calendar.php', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Sistas\' Place', 'url': 'https://sistasplace.org/', 'default_times': ['9:00 PM']},
        {'name': 'Drom', 'url': 'https://dromnyc.com/events/', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'Roulette', 'url': 'https://roulette.org/calendar/', 'default_times': ['8:00 PM']},
        {'name': 'Jazzmobile', 'url': 'https://jazzmobile.org/', 'default_times': ['7:00 PM']},
        {'name': 'The Django', 'url': 'https://www.thedjangonyc.com/events', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Pangea', 'url': 'https://www.pangeanyc.com/music/', 'default_times': ['7:00 PM']},
        {'name': 'The Ear Inn', 'url': 'https://www.theearinn.com/music-schedule/', 'default_times': ['8:00 PM']},
        {'name': 'Shrine', 'url': 'https://shrinenyc.com/', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Chelsea Table + Stage', 'url': 'https://www.chelseatableandstage.com/tickets-shows', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'The Keep', 'url': 'https://www.thekeepny.com/calendar', 'default_times': ['8:00 PM']},
        {'name': 'Joe\'s Pub', 'url': 'https://publictheater.org/joes-pub/', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'Klavierhaus', 'url': 'https://event.klavierhaus.com/k/calendar', 'default_times': ['7:00 PM']},
        {'name': 'Saint Peter\'s Church', 'url': 'https://www.saintpeters.org/events', 'default_times': ['1:00 PM', '7:00 PM']},
        {'name': 'Minton\'s Playhouse', 'url': 'https://www.eventbrite.com/o/mintons-playhouse-76715695933', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'National Sawdust', 'url': 'https://www.nationalsawdust.org/performances-prev', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'The Cutting Room', 'url': 'https://thecuttingroomnyc.com/calendar/', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'Swing 46', 'url': 'https://swing46.nyc/calendar/', 'default_times': ['8:30 PM', '10:30 PM']},
        {'name': 'The Appel Room', 'url': 'https://www.lincolncenter.org/venue/the-appel-room/v/calendar', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Symphony Space', 'url': 'https://www.symphonyspace.org/events', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'Le Poisson Rouge', 'url': 'https://www.lpr.com/', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'Mansions', 'url': 'https://ra.co/clubs/197275', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Knockdown Center', 'url': 'https://knockdown.center/upcoming/', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Jupiter Disco', 'url': 'https://ra.co/clubs/128789', 'default_times': ['Daily 10:00 PM - 4:00 AM']},
        {'name': 'Bossa Nova Civic Club', 'url': 'https://ra.co/clubs/71292', 'default_times': ['Daily 10:00 PM - 4:00 AM']},
        {'name': 'House of Yes', 'url': 'https://www.houseofyes.org/calendar', 'default_times': ['Thursday 10:00 PM - 4:00 AM', 'Friday 10:00 PM - 4:00 AM']},
        {'name': 'Elsewhere', 'url': 'https://www.elsewherebrooklyn.com/calendar', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Good Room', 'url': 'https://donyc.com/venues/good-room', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Nowadays', 'url': 'https://nowadays.nyc/all-events', 'default_times': ['Friday 10:00 PM - 6:00 AM', 'Sunday 3:00 PM - 9:00 PM']},
        {'name': 'Public Records', 'url': 'https://publicrecords.nyc/sound-room/', 'default_times': ['Thursday 7:00 PM - 12:00 AM', 'Saturday 11:00 PM - 4:00 AM']},
        {'name': 'The Sultan Room', 'url': 'https://www.thesultanroom.com/calendar', 'default_times': ['Friday 8:00 PM - 1:00 AM', 'Saturday 8:00 PM - 1:00 AM']},
        {'name': 'Black Flamingo', 'url': 'https://www.blackflamingonyc.com/events', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': '3 Dollar Bill', 'url': 'https://www.3dollarbillbk.com/rsvp', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},

        
    ]

    # Process only 2 venues concurrently to stay under rate limit
    max_workers = 2
    
    print(f"Starting parallel processing with {max_workers} workers")
    
    # Process venues in very small batches
    batch_size = 2
    for i in range(0, len(venues), batch_size):
        batch = venues[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} of {(len(venues) + batch_size - 1)//batch_size}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_venue = {
                executor.submit(process_venue, venue, session): venue['name'] 
                for venue in batch
            }
            
            for future in as_completed(future_to_venue):
                venue_name = future_to_venue[future]
                try:
                    future.result()
                    print(f"Completed processing {venue_name}")
                except Exception as e:
                    print(f"Error processing {venue_name}: {e}")
        
        # Add longer delay between batches
        if i + batch_size < len(venues):
            delay = random.uniform(20, 30)
            print(f"\nWaiting {delay:.1f} seconds before next batch...")
            sleep(delay)

    session.close()
    print("\nAll venues processed")


# -- In store_concert_data, replace your existing block for extracting artist_name, date, times, etc.
# -- with the following safer calls to avoid .strip() on NoneTypes. We also remove .strip() for times
# -- since it's expected to be a list, not a string.

def store_concert_data(session, concert_data_list, venue_info):
    """
    Stores the concert data into the database with deduplication logic.
    """
    venue_name = venue_info['name']
    print(f"\nProcessing {len(concert_data_list)} concerts for {venue_name}")
    
    # Get or create venue
    venue = session.query(Venue).filter_by(name=venue_name).first()
    if not venue:
        venue = Venue(
            name=venue_name,
            address=venue_info.get('address', ''),
            website_url=venue_info['url']
        )
        session.add(venue)
        session.commit()

    for concert_data in concert_data_list:
        print(f"\nProcessing concert:")
        print(f"  Artist: {concert_data.get('artist')}")
        print(f"  Date: {concert_data.get('date')}")
        print(f"  Special Notes: {concert_data.get('special_notes')}")
        
        # Safely retrieve and strip fields
        artist_name = (concert_data.get('artist') or '').strip()
        date_str = (concert_data.get('date') or '').strip()

        if not artist_name or not date_str:
            print("Incomplete concert data (missing artist or date), skipping entry.")
            continue

        try:
            concert_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Check for existing concert with same venue, date and artist
            existing_concert = (
                session.query(Concert)
                .join(Concert.artists)
                .filter(
                    Concert.venue_id == venue.id,
                    Concert.date == concert_date,
                    Artist.name == artist_name
                )
                .first()
            )

            if existing_concert:
                print(f"Concert already exists for {artist_name} at {venue_name} on {concert_date}")
                # Optionally update existing concert with new information
                existing_concert.ticket_link = concert_data.get('ticket_link', existing_concert.ticket_link)
                existing_concert.price_range = concert_data.get('price_range', existing_concert.price_range)
                existing_concert.special_notes = concert_data.get('special_notes', existing_concert.special_notes)
                session.commit()
                continue

            # Get or create artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
                session.commit()

            # Create new concert
            concert = Concert(
                venue_id=venue.id,
                date=concert_date,
                ticket_link=concert_data.get('ticket_link', ''),
                price_range=concert_data.get('price_range', ''),
                special_notes=concert_data.get('special_notes', ''),
            )
            concert.artists.append(artist)

            # Create child ConcertTime rows
            times_list = concert_data.get('times') or venue_info.get('default_times', [])
            for time_str in times_list:
                try:
                    # Try parsing 12-hour format first
                    time_obj = datetime.strptime(time_str, '%I:%M %p').time()
                except ValueError:
                    try:
                        # Try 24-hour format
                        time_obj = datetime.strptime(time_str, '%H:%M').time()
                    except ValueError:
                        print(f"Invalid time format: {time_str}")
                        continue
                concert_time = ConcertTime(time=time_obj)
                concert.times.append(concert_time)

            session.add(concert)
            try:
                session.commit()
                print(f"Added concert: {artist_name} at {venue_name} on {concert_date}")
            except Exception as e:
                print(f"Error committing concert: {e}")
                session.rollback()
                continue

        except Exception as e:
            print(f"Error processing concert data: {e}")
            session.rollback()
            continue

@app.route('/')
def index():
    db = SessionLocal()
    try:
        today = datetime.now().date()
        thirty_days = today + timedelta(days=30)
        
        # Query concerts with relationships
        concerts = (
            db.query(Concert)
            .join(Concert.venue)
            .join(Concert.artists)
            .join(Concert.times)
            .filter(
                Concert.date >= today,
                Concert.date <= thirty_days
            )
            .order_by(Concert.date)
            .all()
        )
        
        # Group concerts by date
        concerts_by_date = {}
        for concert in concerts:
            if concert.date not in concerts_by_date:
                concerts_by_date[concert.date] = []
            concerts_by_date[concert.date].append(concert)
        
        return render_template('index.html', 
                             concerts_by_date=concerts_by_date,
                             today=today)
    finally:
        db.close()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and "server" in sys.argv:
        # Run only the Flask dev server
        app.run(debug=True, host='0.0.0.0')
    else:
        # Run the crawler and then start the server
        main()  # Run the crawler first
        print("\nStarting web server...")
        app.run(debug=True, host='0.0.0.0')  # Then start the server
