from crawler import Crawler
from parser import parse_markdown
from database import Session, SessionLocal, init_db
from models import Artist, Venue, Concert, ConcertTime, User
from datetime import datetime, timedelta, time as datetime_time
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential
from flask import Flask, render_template, session, request, redirect, url_for
from collections import defaultdict
from sqlalchemy import select
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import os
from auth import auth
from dotenv import load_dotenv
from threading import Thread
import atexit
from sqlalchemy.orm import joinedload
import spotipy
from fuzzywuzzy import fuzz
import schedule
from urllib.parse import urlencode, quote
from ics import Calendar, Event
import pytz
import logging
import threading
import signal
import psutil

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev')
app.register_blueprint(auth)

# Force HTTPS
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Add before/after request handlers to redirect HTTP to HTTPS
@app.before_request
def before_request():
    if not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

load_dotenv()

print("Environment Variables:")
print(f"SPOTIFY_CLIENT_ID: {'set' if os.getenv('SPOTIFY_CLIENT_ID') else 'not set'}")
print(f"SPOTIFY_CLIENT_SECRET: {'set' if os.getenv('SPOTIFY_CLIENT_SECRET') else 'not set'}")
print(f"SPOTIFY_REDIRECT_URI: {os.getenv('SPOTIFY_REDIRECT_URI')}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Set SQLAlchemy logging to ERROR only
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)

# Disable propagation to prevent duplicate logs
logging.getLogger('sqlalchemy.engine.base.Engine').propagate = False

# Optional: Keep other noisy loggers quiet
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Add this to prevent duplicate logging
logging.getLogger('sqlalchemy.engine.base.Engine').propagate = False

# Add at the very start of the file, right after imports
def kill_existing_scrapers():
    """Kill any existing scraper threads and processes"""
    try:
        # Get the current process and its parent
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        parent_pid = current_process.parent().pid if current_process.parent() else None
        
        # Kill only other Python processes running scrapers
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip the current process and its parent
                if proc.pid in (current_pid, parent_pid):
                    continue
                    
                # Check if it's a Python process
                if 'python' in proc.name().lower():
                    cmdline = proc.cmdline()
                    # Check if it's running our scraper
                    if any('main.py' in cmd for cmd in cmdline):
                        logging.info(f"Killing old scraper process: {proc.pid}")
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        # Kill threads in current process
        for thread in threading.enumerate():
            if thread != threading.current_thread() and "scraper" in thread.name.lower():
                logging.info(f"Stopping existing scraper thread: {thread.name}")
                thread.join(timeout=1.0)
                
    except Exception as e:
        logging.error(f"Error killing scrapers: {e}")

@app.route('/')
def index():
    db = SessionLocal()
    try:
        # Use Eastern timezone for date comparisons
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        today = now.date()
        three_months = today + timedelta(days=90)
        
        # Get user preferences if logged in
        user_preferences = None
        if 'user_id' in session:
            user = db.query(User).filter_by(id=session['user_id']).first()
            if user:
                user_preferences = {
                    'venues': user.preferred_venues,
                    'neighborhoods': user.preferred_neighborhoods,
                    'genres': user.preferred_genres
                }
        
        # Base query with joins
        query = (
            db.query(Concert)
            .options(
                joinedload(Concert.venue),
                joinedload(Concert.artists),
                joinedload(Concert.times)
            )
        )
        
        # Apply preference filters if user is logged in and has preferences
        if user_preferences:
            if user_preferences['venues']:
                query = query.filter(Concert.venue_id.in_(user_preferences['venues']))
            if user_preferences['neighborhoods']:
                query = query.join(Venue).filter(Venue.neighborhood.in_(user_preferences['neighborhoods']))
            if user_preferences['genres']:
                query = query.join(Venue).filter(Venue.genres.contains(user_preferences['genres']))
        
        # Apply date filters
        query = query.filter(
            Concert.date >= today,
            Concert.date <= three_months,
            (Concert.date > today) | 
            ((Concert.date == today) & 
             (Concert.times.any(ConcertTime.time >= now.time())))
        )
        
        # First get all concerts
        concerts = query.all()
        
        # Organize concerts by date first, then by neighborhood
        concerts_by_date = defaultdict(lambda: defaultdict(list))
        
        for concert in concerts:
            # Get earliest time for sorting
            earliest_time = min((t.time for t in concert.times), default=datetime_time(23, 59))
            
            # Create concert dict with all needed info
            concert_dict = {
                'venue_name': concert.venue.name,
                'artists': concert.artists,
                'times': sorted(concert.times, key=lambda x: x.time),
                'ticket_link': concert.ticket_link,
                'special_notes': concert.special_notes,
                'calendar_links': generate_calendar_links(
                    concert,
                    concert.venue.name,
                    [artist.name for artist in concert.artists]
                ),
                'earliest_time': earliest_time,
                'spotify_score': 0  # You can keep your existing Spotify logic here
            }
            
            # Add to appropriate date and neighborhood
            neighborhood = concert.venue.neighborhood or 'Other'
            concerts_by_date[concert.date][neighborhood].append(concert_dict)
        
        # Sort concerts within each neighborhood by time
        for date in concerts_by_date:
            for neighborhood in concerts_by_date[date]:
                concerts_by_date[date][neighborhood].sort(
                    key=lambda x: x['earliest_time']
                )
        
        # Sort dates
        sorted_dates = sorted(concerts_by_date.keys())
        
        return render_template(
            'index.html',
            concerts_by_date=concerts_by_date,
            sorted_dates=sorted_dates,
            user=user if 'user_id' in session else None
        )
    finally:
        db.close()

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
    
    try:
        # Get or create venue
        venue = get_or_create_venue(session, venue_info)
        
        # Check for existing concerts
        existing_concerts = check_existing_concerts(session, venue_name)
        if existing_concerts:
            logging.info(f"Found {len(existing_concerts)} existing concerts for {venue_name}")
            return
            
        logging.info(f"Processing {venue_name} - new venue")
        
        # Try custom scraper first if available
        concert_data = []
        if has_custom_scraper(venue_name, venue_url):
            logging.info(f"Using custom scraper for {venue_name}")
            concert_data = use_custom_scraper(venue_name, venue_url)
        else:
            # Use Firecrawl for other venues
            concert_data = use_firecrawl(venue_url, venue_name, venue_info)
        
        if not concert_data:
            logging.info(f"No concerts found for {venue_name}")
            return
            
        # Store concert data
        store_concert_data(session, concert_data, venue_info)
        
    except Exception as e:
        logging.error(f"Error processing {venue_name}: {e}")

def is_credit_limit_error(error_msg):
    """Check if the error is due to insufficient Firecrawl credits"""
    credit_limit_indicators = [
        "insufficient credits",
        "payment required",
        "upgrade your plan",
        "for more credits"
    ]
    error_msg = error_msg.lower()
    return any(indicator in error_msg for indicator in credit_limit_indicators)

class FirecrawlCreditLimitError(Exception):
    """Raised when Firecrawl credit limit is reached"""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=10, min=10, max=120),
    reraise=True
)
def scrape_with_retry(crawler, url, venue_name):
    """Attempt to scrape with longer exponential backoff retry"""
    try:
        return crawler.scrape_venue(url)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:  # Rate limit error
            logging.info(f"Rate limit hit for {venue_name}, backing off...")
            time.sleep(random.uniform(15, 20))
        elif is_credit_limit_error(error_msg):
            raise FirecrawlCreditLimitError("Firecrawl credit limit reached")
        raise

def use_firecrawl(venue_url, venue_name, venue_info):
    """Use Firecrawl to scrape a venue"""
    try:
        crawler = Crawler()
        markdown_content = scrape_with_retry(crawler, venue_url, venue_name)
        if not markdown_content:
            return []
        return parse_markdown(markdown_content, venue_info)
    except FirecrawlCreditLimitError:
        logging.error("Firecrawl credit limit reached - stopping scraper")
        # Signal the main loop to stop
        threading.current_thread().stop_flag = True
        return []
    except Exception as e:
        logging.error(f"Error using Firecrawl: {e}")
        return []

def calculate_scrape_params(venue_count):
    """Calculate scraping parameters based on rate limits
    - 3000 pages/month = ~100 pages/day
    - 20 scrapes/minute = 1 scrape per 3 seconds
    """
    RATE_LIMIT_PER_MIN = 20
    SECONDS_PER_MIN = 60
    MIN_DELAY = SECONDS_PER_MIN / RATE_LIMIT_PER_MIN  # 3 seconds minimum between requests
    
    # Add safety margin - use 15 per minute instead of 20
    SAFE_RATE_LIMIT = 15
    SAFE_DELAY = SECONDS_PER_MIN / SAFE_RATE_LIMIT  # 4 seconds between requests
    
    # Calculate batch size based on venue count
    # If we have 60 venues, and want to scrape each daily, that's 60/24 = 2.5 venues per hour
    HOURS_PER_DAY = 24
    venues_per_hour = venue_count / HOURS_PER_DAY
    batch_size = max(1, min(3, round(venues_per_hour)))  # Between 1 and 3 venues per batch
    
    return {
        'batch_size': batch_size,
        'request_delay': SAFE_DELAY,
        'batch_delay': 60  # 1 minute between batches
    }

def main():
    """Main function that orchestrates the crawling, parsing, and storing of concert data."""
    session = Session()
    
    # List of venue websites to crawl
    venues = [
        {'name': 'IFC Center',
         'url': 'https://www.ifccenter.com/',
         'default_times': [],  # Movies have variable times
         'neighborhood': 'Greenwich Village',
         'genres': ['Movies']
        },
        {'name': 'Film Forum',  # Add Film Forum
         'url': 'https://filmforum.org/now_playing',
         'default_times': [],  # Movies have variable times
         'neighborhood': 'Greenwich Village',
         'genres': ['Movies']
        },
        {'name': 'Quad Cinema',  # Add Quad Cinema
         'url': 'https://quadcinema.com',
         'default_times': [],  # Movies have variable times
         'neighborhood': 'Greenwich Village',
         'genres': ['Movies']
        },
        {'name': 'Mansions', 'url': 'https://ra.co/clubs/197275', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Close Up', 
         'url': 'https://www.closeupnyc.com/calendar', 
         'default_times': ['7:00 PM', '9:00 PM']
        },
        {'name': 'Knockdown Center', 'url': 'https://knockdown.center/upcoming/', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Village Vanguard', 'url': 'https://villagevanguard.com', 'default_times': ['8:00 PM', '10:00 PM']},
        {'name': 'Jupiter Disco', 'url': 'https://ra.co/clubs/128789', 'default_times': ['Daily 10:00 PM - 4:00 AM']},
        {'name': 'Bossa Nova Civic Club', 'url': 'https://ra.co/clubs/71292', 'default_times': ['Daily 10:00 PM - 4:00 AM']},
        {'name': 'House of Yes', 'url': 'https://www.houseofyes.org/calendar', 'default_times': ['Thursday 10:00 PM - 4:00 AM', 'Friday 10:00 PM - 4:00 AM']},
        {'name': 'Elsewhere', 'url': 'https://www.elsewherebrooklyn.com/calendar', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Good Room', 'url': 'https://donyc.com/venues/good-room', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Nowadays', 'url': 'https://ra.co/clubs/105873', 'default_times': ['Friday 10:00 PM - 6:00 AM', 'Sunday 3:00 PM - 9:00 PM']},
        {'name': 'Public Records', 'url': 'https://publicrecords.nyc', 'default_times': ['Thursday 7:00 PM - 12:00 AM', 'Saturday 11:00 PM - 4:00 AM']},
        {'name': 'The Sultan Room', 'url': 'https://www.thesultanroom.com/calendar', 'default_times': ['Friday 8:00 PM - 1:00 AM', 'Saturday 8:00 PM - 1:00 AM']},
        {'name': 'Black Flamingo', 'url': 'https://www.blackflamingonyc.com/events', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': '3 Dollar Bill', 'url': 'https://www.3dollarbillbk.com/rsvp', 'default_times': ['Friday 10:00 PM - 4:00 AM', 'Saturday 10:00 PM - 4:00 AM']},
        {'name': 'Smalls Jazz Club', 'url': 'https://www.smallslive.com', 'default_times': ['7:30 PM', '10:00 PM', '11:30 PM']},
        {'name': 'Mezzrow Jazz Club', 'url': 'https://mezzrow.com/', 'default_times': ['7:30 PM', '9:00 PM', '10:30 PM']},
        {'name': 'Dizzy\'s Club', 'url': 'https://jazz.org/concerts-events/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'The Jazz Gallery', 'url': 'https://jazzgallery.org/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Blue Note', 'url': 'https://www.bluenotejazz.com/nyc/shows', 'default_times': ['8:00 PM', '10:30 PM']},
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
        {'name': 'The Appel Room', 'url': 'https://www.lincolncenter.org/venue/the-appel-room/v/calendar', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Symphony Space', 'url': 'https://www.symphonyspace.org/events', 'default_times': ['7:00 PM', '9:00 PM']},
        {'name': 'Le Poisson Rouge', 'url': 'https://www.lpr.com/', 'default_times': ['7:00 PM', '9:30 PM']},
        {'name': 'Film at Lincoln Center', 'url': 'https://www.filmlinc.org/', 'default_times': ['7:00 PM', '9:30 PM']}
    ]
    
    # Calculate scraping parameters
    params = calculate_scrape_params(len(venues))
    print(f"\nScraping parameters:")
    print(f"Batch size: {params['batch_size']}")
    print(f"Request delay: {params['request_delay']:.1f} seconds")
    print(f"Batch delay: {params['batch_delay']} seconds")
    
    # Process venues in small batches
    for i in range(0, len(venues), params['batch_size']):
        batch = venues[i:i+params['batch_size']]
        print(f"\nProcessing batch {i//params['batch_size'] + 1} of {(len(venues) + params['batch_size'] - 1)//params['batch_size']}")
        
        with ThreadPoolExecutor(max_workers=1) as executor:  # Process one at a time
            for venue in batch:
                future = executor.submit(process_venue, venue, session)
                try:
                    future.result()
                    print(f"Completed processing {venue['name']}")
                    # Add delay between requests
                    time.sleep(params['request_delay'])
                except Exception as e:
                    print(f"Error processing {venue['name']}: {e}")
        
        # Add delay between batches
        if i + params['batch_size'] < len(venues):
            print(f"\nWaiting {params['batch_delay']} seconds before next batch...")
            time.sleep(params['batch_delay'])

    session.close()
    print("\nAll venues processed")

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

def run_scraper_schedule():
    """Run the scraper on a schedule"""
    def scheduled_job():
        logging.info("Running scheduled scraper")
        try:
            main()
            logging.info("Scheduled scraper completed successfully")
        except Exception as e:
            logging.error(f"Error in scheduled scraper: {e}")

    # Add stop flag to thread
    threading.current_thread().stop_flag = False
    
    # Schedule the job to run daily at 4 AM
    schedule.every().day.at("04:00").do(scheduled_job)
    
    # Run the scraper immediately on startup
    logging.info("Running initial scraper")
    scheduled_job()
    
    while not getattr(threading.current_thread(), 'stop_flag', False):
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def start_scraper_thread():
    """Start the background scraper thread"""
    scraper_thread = Thread(
        target=run_scraper_schedule,
        name="concert-scraper-thread",
        daemon=True
    )
    scraper_thread.start()
    return scraper_thread

def initialize_app():
    """Initialize the application"""
    init_db()
    
    # Clean placeholder artists on startup
    print("\nCleaning placeholder artists from database...")
    clean_placeholder_artists()
    
    # Start the scraper thread
    scraper_thread = start_scraper_thread()
    atexit.register(lambda: scraper_thread.join(timeout=1.0))

def normalize_artist_name(name):
    """Normalize artist name for better matching"""
    # Remove common words that might cause false matches
    name = name.lower().strip()
    skip_words = ['trio', 'quartet', 'quintet', 'band', 'orchestra', 'ensemble', 'presents', 'featuring']
    for word in skip_words:
        name = name.replace(f' {word}', '')
    return name

def clean_placeholder_artists():
    db = SessionLocal()
    try:
        # Find problematic artists
        placeholder_artists = db.query(Artist).filter(
            (Artist.name.in_(['TBA', 'Artist Name'])) |
            (Artist.name.like('%TBA%')) |
            (Artist.name == '') |
            (Artist.name.is_(None))
        ).all()
        
        print(f"Found {len(placeholder_artists)} placeholder artists:")
        for artist in placeholder_artists:
            print(f"- {artist.name}")
            
        # Delete the artists (this will automatically handle concert_artists relationships)
        for artist in placeholder_artists:
            db.delete(artist)
            
        db.commit()
        print("Successfully cleaned placeholder artists from database")
        
    except Exception as e:
        print(f"Error cleaning database: {e}")
        db.rollback()
    finally:
        db.close()

@app.route('/preferences')
def preferences():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        venues = db.query(Venue).order_by(Venue.name).all()
        
        # Define known neighborhoods
        known_neighborhoods = [
            'Greenwich Village',
            'Theater District',
            'Upper West Side',
            'Flatiron District',
            'Bushwick',
            'Williamsburg',
            'Downtown Brooklyn',
            'Midtown',
            'Lower East Side',
            'East Village',
            'Chelsea'
        ]
        
        # Get neighborhoods from both venues and known list
        venue_neighborhoods = set(venue.neighborhood for venue in venues if venue.neighborhood)
        all_neighborhoods = sorted(venue_neighborhoods.union(known_neighborhoods))
        
        # Simplified genres
        genres = ['Jazz', 'Clubs', 'Galleries', 'Museums']
        
        return render_template('preferences.html',
                             user=user,
                             venues=venues,
                             neighborhoods=all_neighborhoods,
                             genres=genres)
    finally:
        db.close()

@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        
        # Update user preferences
        user.preferred_venues = request.form.getlist('venues')
        user.preferred_neighborhoods = request.form.getlist('neighborhoods')
        user.preferred_genres = request.form.getlist('genres')
        
        db.commit()
        return redirect(url_for('index'))
    finally:
        db.close()

def generate_calendar_links(concert, venue_name, artist_names):
    """Generate Google Calendar and iCal links for a concert"""
    
    # Format the event title and description
    title = f"{', '.join(artist_names)} at {venue_name}"
    description = f"Artists: {', '.join(artist_names)}\n"
    if concert.price_range:
        description += f"Price: {concert.price_range}\n"
    if concert.ticket_link:
        description += f"Tickets: {concert.ticket_link}\n"
    if concert.special_notes:
        description += f"Notes: {concert.special_notes}"
        
    # Get the first show time, or use 8 PM as default
    default_time = datetime_time(20, 0)  # Use renamed datetime.time
    show_time = concert.times[0].time if concert.times else default_time
    
    # Create datetime objects for start and end
    start_dt = datetime.combine(concert.date, show_time)
    end_dt = start_dt + timedelta(hours=2)  # Assume 2-hour shows
    
    # Google Calendar link
    gcal_params = {
        'action': 'TEMPLATE',
        'text': title,
        'details': description,
        'location': venue_name,
        'dates': f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
    }
    gcal_url = "https://calendar.google.com/calendar/render?" + urlencode(gcal_params)
    
    # iCal link (using ics library)
    calendar = Calendar()
    event = Event()
    event.name = title
    event.begin = start_dt
    event.end = end_dt
    event.description = description
    event.location = venue_name
    calendar.events.add(event)
    ical_data = calendar.serialize()
    
    return {
        'gcal': gcal_url,
        'ical': f"data:text/calendar;charset=utf8,{quote(ical_data)}"
    }

def get_or_create_venue(session, venue_info):
    """Get existing venue or create a new one"""
    venue = session.query(Venue).filter_by(name=venue_info['name']).first()
    if not venue:
        venue = Venue(
            name=venue_info['name'],
            website_url=venue_info['url'],
            neighborhood=venue_info.get('neighborhood', ''),
            genres=venue_info.get('genres', [])
        )
        session.add(venue)
        session.commit()
    return venue

def check_existing_concerts(session, venue_name):
    """Check if venue has any upcoming concerts"""
    now = datetime.now(pytz.UTC)
    venue = session.query(Venue).filter_by(name=venue_name).first()
    if venue and venue.last_scraped:
        venue_last_scraped = venue.last_scraped.replace(tzinfo=pytz.UTC)
        time_since_scrape = now - venue_last_scraped
        
        # Check if venue has any upcoming concerts
        upcoming_concerts = session.query(Concert).join(Venue).filter(
            Venue.name == venue_name,
            Concert.date >= datetime.now().date()
        ).all()
        
        # Return concerts if recently scraped AND has upcoming concerts
        if time_since_scrape < timedelta(hours=24) and upcoming_concerts:
            return upcoming_concerts
    return []

def has_custom_scraper(venue_name, venue_url):
    """Check if venue has a custom scraper or uses RA"""
    custom_scrapers = {
        'Close Up': True,
        'Village Vanguard': True,
        'Knockdown Center': True,
        'IFC Center': True,
        'Film Forum': True,
        'Quad Cinema': True,
        'Film at Lincoln Center': True  # Add Film at Lincoln Center
    }
    return custom_scrapers.get(venue_name, False) or 'ra.co' in venue_url

def use_custom_scraper(venue_name, venue_url):
    """Use the appropriate custom scraper for a venue"""
    # Check for RA venues first
    if 'ra.co' in venue_url:
        from ra_scraper import scrape_ra
        return scrape_ra(venue_url)
        
    # Use venue-specific scrapers
    if venue_name == 'Close Up':
        from closeup_scraper import scrape_closeup
        return scrape_closeup()
    elif venue_name == 'Village Vanguard':
        from vanguard_scraper import scrape_vanguard
        return scrape_vanguard()
    elif venue_name == 'Knockdown Center':
        from knockdown_scraper import scrape_knockdown
        return scrape_knockdown()
    elif venue_name == 'IFC Center':
        from ifc_scraper import scrape_ifc
        return scrape_ifc()
    elif venue_name == 'Film Forum':
        from film_forum_scraper import scrape_film_forum
        return scrape_film_forum()
    elif venue_name == 'Quad Cinema':
        from quad_scraper import scrape_quad
        return scrape_quad()
    elif venue_name == 'Film at Lincoln Center':  # Add Film at Lincoln Center
        from lincoln_scraper import scrape_lincoln
        return scrape_lincoln()
    return []

if __name__ == '__main__':
    import sys
    from werkzeug.serving import run_simple
    from werkzeug.middleware.proxy_fix import ProxyFix
    
    # Kill any existing scrapers first
    kill_existing_scrapers()
    
    # Wrap the app to fix protocol headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    
    # Parse command line arguments
    run_scraper = True
    if len(sys.argv) > 1:
        if "no-scrape" in sys.argv:
            run_scraper = False
            logging.info("Starting web server without scraper")
        elif "server" in sys.argv:
            logging.info("Starting web server with scraper")
    
    # Initialize based on arguments
    init_db()
    if run_scraper:
        # Kill scrapers again just to be sure
        kill_existing_scrapers()
        scraper_thread = start_scraper_thread()
        atexit.register(lambda: scraper_thread.join(timeout=1.0))
    
    # Run with SSL
    run_simple('0.0.0.0', 5000, app,
               use_reloader=True,
               use_debugger=True,
               use_evalex=True,
               threaded=True)
