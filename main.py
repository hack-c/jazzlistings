from crawler import Crawler
from parser import parse_markdown
from database import Session, SessionLocal, init_db
from models import Artist, Venue, Concert, ConcertTime, User
from datetime import datetime, timedelta, time as datetime_time
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential
from flask import Flask, render_template, session, request, redirect, url_for, flash
from collections import defaultdict
from sqlalchemy import select, String
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
import sys

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

# Configure root logger to only show WARNING and above
logging.basicConfig(level=logging.WARNING)

# Create a custom logger for application events
app_logger = logging.getLogger('concert_app')
app_logger.setLevel(logging.INFO)

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
@app.route('/<show_all>')
def index(show_all=None):
    db = SessionLocal()
    try:
        # Add debug logging
        logging.info("Checking venue data:")
        venues = db.query(Venue).all()
        for venue in venues:
            logging.info(f"Venue: {venue.name}, Neighborhood: {venue.neighborhood}, Genres: {venue.genres}")

        # Use Eastern timezone for date comparisons
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        today = now.date()
        three_months = today + timedelta(days=90)
        
        # Check if we should show all concerts
        show_all_concerts = (show_all == 'all' or request.args.get('show_all') == 'true')
        
        # Get user preferences if logged in
        user_preferences = None
        if 'user_id' in session and not show_all_concerts:
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
        if user_preferences and (user_preferences['venues'] or user_preferences['neighborhoods'] or user_preferences['genres']):
            # Create a list to collect filter conditions
            filter_conditions = []
            
            # For each preference type, add a condition
            if user_preferences['venues']:
                filter_conditions.append(Concert.venue_id.in_(user_preferences['venues']))
                
            if user_preferences['neighborhoods']:
                # Ensure we have the Venue join
                if not filter_conditions:  # Only add join if not already joined for venues
                    query = query.join(Venue)
                filter_conditions.append(Venue.neighborhood.in_(user_preferences['neighborhoods']))
                
            if user_preferences['genres']:
                # Ensure we have the Venue join
                if not filter_conditions:  # Only add join if not already joined
                    query = query.join(Venue)
                
                # For each preferred genre, check if it's in the venue's genre list
                genre_conditions = []
                for genre in user_preferences['genres']:
                    # This properly checks if a single genre is in the JSON array
                    genre_conditions.append(Venue.genres.cast(String).like(f'%"{genre}"%'))
                
                # Combine with OR logic between genres
                if genre_conditions:
                    from sqlalchemy import or_
                    filter_conditions.append(or_(*genre_conditions))
            
            # Apply filters with OR logic between different preference types
            if filter_conditions:
                from sqlalchemy import or_
                query = query.filter(or_(*filter_conditions))
        
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
        
        # Calculate total number of events
        event_count = sum(len(concerts) for date in concerts_by_date for concerts in concerts_by_date[date].values())
        
        # Add a flash message if this is the show_all view and there are events
        if show_all_concerts and event_count > 0 and user_preferences:
            flash("Showing all events. Your preference filters are currently disabled.")
        
        return render_template(
            'index.html',
            concerts_by_date=concerts_by_date,
            sorted_dates=sorted_dates,
            user=user if 'user_id' in session else None,
            event_count=event_count,
            show_all=show_all
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
    """Process a single venue with strict rate limiting and improved error handling"""
    venue_name = venue_info['name']
    venue_url = venue_info['url']
    
    # Create a nested session to handle transaction isolation
    nested_session = Session()
    
    try:
        # Get or create venue
        venue = get_or_create_venue(nested_session, venue_info)
        
        # Check if this venue was recently scraped (within the last 24 hours)
        if venue.last_scraped:
            # Make timezone-aware comparison to avoid "offset-naive and offset-aware" error
            # Use timezone from pytz which is already imported
            now = datetime.now(pytz.UTC)
            # Ensure venue.last_scraped has timezone info
            last_scraped = venue.last_scraped.replace(tzinfo=pytz.UTC) if venue.last_scraped.tzinfo is None else venue.last_scraped
            time_since_scrape = now - last_scraped
            if time_since_scrape < timedelta(hours=24):
                logging.info(f"Skipping {venue_name} - was scraped {time_since_scrape.total_seconds() / 3600:.1f} hours ago")
                nested_session.close()
                return
        
        logging.info(f"Processing {venue_name}")
        
        concert_data = []
        
        # Handle RA venues differently
        if 'ra.co' in venue_url:
            # For RA venues, determine scraping strategy
            scrape_strategy = os.environ.get('RA_SCRAPE_STRATEGY', 'auto').lower()
            logging.info(f"Using RA scrape strategy: {scrape_strategy}")
            
            if scrape_strategy == 'requests':
                # Try only the requests method (fastest)
                from ra_scraper import scrape_ra_requests
                concert_data = scrape_ra_requests(venue_url)
                
            elif scrape_strategy == 'selenium':
                # Use full selenium approach (most thorough)
                from ra_scraper import scrape_ra
                concert_data = scrape_ra(venue_url)
                
            else:  # 'auto' or any other value
                # Try requests first, then fall back to selenium if needed
                from ra_scraper import scrape_ra_requests, scrape_ra
                
                # First try with requests (faster)
                logging.info(f"First trying requests method for {venue_name}...")
                concert_data = scrape_ra_requests(venue_url)
                
                # If that fails, try selenium
                if not concert_data:
                    logging.info(f"Requests method failed for {venue_name}, trying Selenium...")
                    concert_data = scrape_ra(venue_url)
        
        elif has_custom_scraper(venue_name, venue_url):
            concert_data = use_custom_scraper(venue_name, venue_url)
        else:
            crawler = Crawler()
            markdown_content = crawler.scrape_venue(venue_url)
            if markdown_content:
                concert_data = parse_markdown(markdown_content, venue_info)
        
        if concert_data:
            try:
                # We always store/update concert data, even if the venue was recently scraped
                num_concerts = len(concert_data)
                store_concert_data(nested_session, concert_data, venue_info)
                logging.info(f"Completed processing {venue_name} - found {num_concerts} events")
                # Update last_scraped timestamp with timezone-aware datetime
                venue.last_scraped = datetime.now(pytz.UTC)
                nested_session.commit()
            except Exception as e:
                logging.error(f"Error storing concert data for {venue_name}: {e}")
                nested_session.rollback()
        else:
            logging.info(f"No concerts found for {venue_name}")
            
    except Exception as e:
        logging.error(f"Error processing {venue_name}: {e}")
        # Ensure we always rollback on error
        try:
            nested_session.rollback()
        except Exception as rollback_error:
            logging.error(f"Error during rollback for {venue_name}: {rollback_error}")
    finally:
        # Always close the session
        try:
            nested_session.close()
        except Exception as close_error:
            logging.error(f"Error closing session for {venue_name}: {close_error}")

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

def process_venue_batch(batch, session):
    """Process a batch of venues with improved error handling"""
    # Skip if we're in the reloader process
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        return
        
    logging.info(f"Processing batch of {len(batch)} venues")
    processed_venues = set()  # Track which venues we've processed
    
    # Separate RA venues and non-RA venues
    ra_venues = [v for v in batch if 'ra.co' in v['url']]
    other_venues = [v for v in batch if 'ra.co' not in v['url']]
    
    # Randomize order of RA venues
    random.shuffle(ra_venues)
    
    # Log threading information
    logging.info(f"PERFORMANCE: Using ThreadPoolExecutor with max_workers=1 (sequential processing)")
    logging.info(f"PERFORMANCE: Batch details - {len(other_venues)} non-RA venues, {len(ra_venues)} RA venues")
    
    # Process non-RA venues first
    with ThreadPoolExecutor(max_workers=1) as executor:
        for venue_info in other_venues + ra_venues:  # Process regular venues, then RA
            venue_name = venue_info['name']
            
            if venue_name in processed_venues:
                logging.debug(f"Skipping already processed venue: {venue_name}")
                continue
                
            try:
                # Create a fresh session for each venue to avoid transaction issues
                # The nested process_venue function will create its own session
                future = executor.submit(process_venue, venue_info, None)
                future.result()
                processed_venues.add(venue_name)
                logging.info(f"Completed processing {venue_name}")
                
                # Add timing logs
                scrape_end_time = datetime.now()
                
                # Longer delay for RA venues
                if 'ra.co' in venue_info['url']:
                    delay = random.uniform(30, 60)
                    logging.info(f"PERFORMANCE: RA venue {venue_name} processed, about to sleep {delay:.1f} seconds...")
                    venue_type = "RA"
                    time.sleep(delay)
                else:
                    delay = random.uniform(1, 3)
                    logging.info(f"PERFORMANCE: Non-RA venue {venue_name} processed, about to sleep {delay:.1f} seconds...")
                    venue_type = "Standard"
                    time.sleep(delay)
                    
                # Log total time including sleep
                total_time = (datetime.now() - scrape_end_time).total_seconds() + delay
                logging.info(f"PERFORMANCE: {venue_type} venue {venue_name} - sleep overhead: {delay:.1f}s, total wait: {total_time:.1f}s")
                    
            except Exception as e:
                logging.error(f"Error processing {venue_name}: {e}")
                # Continue with next venue instead of failing the whole batch

def main():
    """Main function that orchestrates the crawling, parsing, and storing of concert data."""
    # We don't need a global session anymore since each venue creates its own
    # session = Session()
    
    # List of venue websites to crawl
    venues = [
        {'name': 'Mansions', 
         'url': 'https://ra.co/clubs/197275', 
         'default_times': ['22:00']
        },
        {'name': 'Jupiter Disco', 
         'url': 'https://ra.co/clubs/128789', 
         'default_times': ['22:00']
        },
        {'name': 'Bossa Nova Civic Club', 
         'url': 'https://ra.co/clubs/71292', 
         'default_times': ['22:00']
        },
        {'name': 'Nowadays', 
         'url': 'https://ra.co/clubs/105873', 
         'default_times': ['15:00', '20:00']
        },
        {'name': 'Elsewhere', 
         'url': 'https://ra.co/clubs/139960', 
         'default_times': ['22:00']
        },
        {'name': 'Pianos', 
         'url': 'https://ra.co/clubs/8400', 
         'default_times': ['22:00']
        },
        {'name': 'Mood Ring', 
         'url': 'https://ra.co/clubs/141852', 
         'default_times': ['22:00']
        },
        {'name': '99 Scott', 
         'url': 'https://ra.co/clubs/103503', 
         'default_times': ['22:00']
        },
        {'name': 'Good Room', 
         'url': 'https://ra.co/clubs/97606', 
         'default_times': ['22:00']
        },        
        {'name': 'Public Records', 
         'url': 'https://publicrecords.nyc', 
         'default_times': ['20:00']
        },
        {'name': 'The Sultan Room', 
         'url': 'https://www.thesultanroom.com/calendar', 
         'default_times': ['20:00']
        },
        {'name': 'Village Vanguard', 
         'url': 'https://villagevanguard.com', 
         'default_times': ['20:00', '22:00']
        },
        {'name': 'Bar Bayeux', 'url': 'https://www.barbayeux.com/jazz/', 'default_times': ['8:00 PM', '9:30 PM']},
        {'name': 'Knockdown Center', 
         'url': 'https://knockdown.center/upcoming/', 
         'default_times': ['22:00']
        },
        {'name': 'House of Yes', 
         'url': 'https://www.houseofyes.org/calendar', 
         'default_times': ['22:00']
        },
        {'name': 'Black Flamingo', 'url': 'https://www.blackflamingonyc.com/events', 'default_times': ['22:00']},
        {'name': '3 Dollar Bill', 'url': 'https://www.3dollarbillbk.com/rsvp', 'default_times': ['22:00']},
        {'name': 'Smalls Jazz Club', 'url': 'https://www.smallslive.com', 'default_times': ['7:30 PM', '10:00 PM', '11:30 PM']},
        {'name': 'Mezzrow Jazz Club', 'url': 'https://mezzrow.com/', 'default_times': ['7:30 PM', '9:00 PM', '10:30 PM']},
        {'name': 'Dizzy\'s Club', 'url': 'https://jazz.org/concerts-events/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'The Jazz Gallery', 'url': 'https://jazzgallery.org/calendar/', 'default_times': ['7:30 PM', '9:30 PM']},
        {'name': 'Blue Note', 'url': 'https://www.bluenotejazz.com/nyc/shows', 'default_times': ['8:00 PM', '10:30 PM']},
        {'name': 'Ornithology Jazz Club', 'url': 'https://www.ornithologyjazzclub.com/events-2/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        {'name': 'Ornithology Cafe', 'url': 'https://www.ornithologyjazzclub.com/new-page-1/', 'default_times': ['6:30 PM', '8:30 PM', '9:00 PM']},
        {'name': 'Bar LunÀtico', 'url': 'https://www.barlunatico.com/music/', 'default_times': ['9:00 PM', '10:15 PM']},
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
        {'name': 'Barbès', 'url': 'https://viewcyembed.com/barbes/000000/FFFCFC/850505', 'default_times': ['8:00 PM', '10:00 PM']},
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
        {'name': 'Close Up', 
         'url': 'https://www.closeupnyc.com/calendar', 
         'default_times': ['19:00', '21:00']
        },
        {'name': 'Film at Lincoln Center', 'url': 'https://www.filmlinc.org/', 'default_times': ['7:00 PM', '9:30 PM']},
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
        {'name': 'Market Hotel', 'url': 'https://ra.co/clubs/19281', 'default_times': ['11:00 PM'], 'neighborhood': 'Bushwick', 'genres': ['Clubs']},
        {'name': 'Paragon', 'url': 'https://ra.co/clubs/195815', 'default_times': ['11:00 PM'], 'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    ]
    
    # Shuffle venues for randomized scraping order
    random.shuffle(venues)
    
    # Calculate scraping parameters
    params = calculate_scrape_params(len(venues))
    print(f"\nScraping parameters:")
    print(f"Batch size: {params['batch_size']}")
    print(f"Request delay: {params['request_delay']:.1f} seconds")
    print(f"Batch delay: {params['batch_delay']} seconds")
    print(f"Venues will be processed in random order")
    
    # Process venues in small batches
    for i in range(0, len(venues), params['batch_size']):
        batch = venues[i:i+params['batch_size']]
        print(f"\nProcessing batch {i//params['batch_size'] + 1} of {(len(venues) + params['batch_size'] - 1)//params['batch_size']}")
        
        # Pass None for session parameter since each venue creates its own session
        process_venue_batch(batch, None)
        
        # Add delay between batches
        if i + params['batch_size'] < len(venues):
            print(f"\nWaiting {params['batch_delay']} seconds before next batch...")
            time.sleep(params['batch_delay'])

    print("\nAll venues processed")

def store_concert_data(session, concert_data_list, venue_info):
    """
    Stores the concert data into the database with deduplication logic.
    When a concert with the same venue, artist, date, and time is found, it will update
    the existing concert rather than creating a new one.
    """
    venue_name = venue_info['name']
    print(f"\nProcessing {len(concert_data_list)} concerts for {venue_name}")
    
    # Get or create venue
    venue = session.query(Venue).filter_by(name=venue_name).first()
    if not venue:
        venue = Venue(
            name=venue_name,
            address=venue_info.get('address', ''),
            website_url=venue_info['url'],
            neighborhood=venue_info.get('neighborhood', ''),
            genres=venue_info.get('genres', [])
        )
        session.add(venue)
        session.commit()
    else:
        # Update venue fields if they're missing but provided in venue_info
        if not venue.neighborhood and venue_info.get('neighborhood'):
            venue.neighborhood = venue_info.get('neighborhood')
        if not venue.genres and venue_info.get('genres'):
            venue.genres = venue_info.get('genres')
        if venue_info.get('address') and not venue.address:
            venue.address = venue_info.get('address')
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
            
            # Parse times for the concert to check for duplicates
            times_list = concert_data.get('times') or venue_info.get('default_times', [])
            processed_times = []
            
            # Process all time strings into time objects for comparison
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
                processed_times.append(time_obj)
            
            # Add detailed logging to debug duplication issues
            print(f"\nCHECKING FOR DUPLICATES: {venue_name}, {concert_date}, '{artist_name}', times: {processed_times}")
            
            # Get or create artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
                session.commit()
            
            # Check for existing concert with same venue, date, artist
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
            
            # If we found a match, check if it has the same time(s)
            if existing_concert:
                existing_artists = [a.name for a in existing_concert.artists]
                existing_times = [t.time for t in existing_concert.times]
                
                print(f"MATCH FOUND: {venue_name}, {concert_date}, Artists: {existing_artists}")
                print(f"Existing times: {existing_times}, New times: {processed_times}")
                
                # Update the existing concert with new information
                existing_concert.ticket_link = concert_data.get('ticket_link', existing_concert.ticket_link)
                existing_concert.price_range = concert_data.get('price_range', existing_concert.price_range)
                existing_concert.special_notes = concert_data.get('special_notes', existing_concert.special_notes)
                existing_concert.updated_at = datetime.now()  # Update the timestamp
                
                # Update times if they've changed
                if set(processed_times) != set(existing_times):
                    print(f"Times have changed, updating concert times")
                    
                    # Delete existing times
                    for time in existing_concert.times:
                        session.delete(time)
                    
                    # Add new times
                    for time_obj in processed_times:
                        concert_time = ConcertTime(time=time_obj)
                        existing_concert.times.append(concert_time)
                
                session.commit()
                print(f"Updated existing concert: {artist_name} at {venue_name} on {concert_date}")
                continue

            # Create new concert if no duplicate found
            concert = Concert(
                venue_id=venue.id,
                date=concert_date,
                ticket_link=concert_data.get('ticket_link', ''),
                price_range=concert_data.get('price_range', ''),
                special_notes=concert_data.get('special_notes', ''),
            )
            concert.artists.append(artist)

            # Create child ConcertTime rows
            for time_obj in processed_times:
                concert_time = ConcertTime(time=time_obj)
                concert.times.append(concert_time)

            session.add(concert)
            try:
                session.commit()
                print(f"Added new concert: {artist_name} at {venue_name} on {concert_date}")
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
    
    # Run constraint removal migration
    print("\nChecking database constraints...")
    try:
        from migrations.remove_unique_constraint import run_migration
        if run_migration():
            print("Successfully removed unique constraint")
        else:
            print("Note: unique constraint may still be present")
    except Exception as e:
        print(f"Warning: Could not run constraint migration: {e}")
    
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

@app.route('/admin/update_venues', methods=['GET'])
def admin_update_venues():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    try:
        update_venue_data()
        flash("Venue data updated successfully!")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error updating venue data: {str(e)}")
        return redirect(url_for('index'))

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            flash("User not found.")
            return redirect(url_for('auth.login'))
        
        if request.method == 'POST':
            try:
                # Convert venue IDs to strings to ensure consistent storage
                # This prevents issues with type comparison in templates
                venue_ids = [str(id) for id in request.form.getlist('venues')]
                neighborhoods = request.form.getlist('neighborhoods')
                genres = request.form.getlist('genres')
                
                # Update user preferences
                user.preferred_venues = venue_ids
                user.preferred_neighborhoods = neighborhoods
                user.preferred_genres = genres
                
                db.commit()
                flash("Preferences saved successfully!")
                return redirect(url_for('index'))
            except Exception as e:
                db.rollback()
                flash(f"Error saving preferences: {str(e)}")
                logging.error(f"Error saving preferences: {str(e)}")
        
        # Get all venues for the form
        venues = db.query(Venue).order_by(Venue.name).all()
        
        # Get unique neighborhoods - ensure they're not empty/None
        neighborhoods = db.query(Venue.neighborhood).distinct().order_by(Venue.neighborhood)
        neighborhoods = [n[0] for n in neighborhoods if n[0] and n[0].strip()]
        
        # Get unique genres from all venues
        all_genres = set()
        for venue in venues:
            if venue.genres and isinstance(venue.genres, list):
                all_genres.update(venue.genres)
        
        # Make sure Movies is included
        all_genres.add('Movies')
        
        # Sort genres alphabetically
        genres = sorted(all_genres)
        
        return render_template(
            'preferences.html',
            user=user,
            venues=venues,
            neighborhoods=neighborhoods,
            genres=genres
        )
    except Exception as e:
        logging.error(f"Error in preferences route: {str(e)}")
        flash("An error occurred. Please try again.")
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
    """Get existing venue or create a new one, and update missing fields"""
    # If session is None, create a new one
    session_created = False
    if session is None:
        session = Session()
        session_created = True
    
    try:
        venue = session.query(Venue).filter_by(name=venue_info['name']).first()
        if not venue:
            # Create new venue with all available info
            venue = Venue(
                name=venue_info['name'],
                website_url=venue_info['url'],
                address=venue_info.get('address', ''),
                neighborhood=venue_info.get('neighborhood', ''),
                genres=venue_info.get('genres', [])
            )
            session.add(venue)
            session.commit()
        else:
            # Update venue fields if they're missing or empty but provided in venue_info
            updated = False
            
            if venue_info.get('neighborhood') and (not venue.neighborhood or venue.neighborhood == ''):
                venue.neighborhood = venue_info.get('neighborhood')
                updated = True
                
            if venue_info.get('genres') and (not venue.genres or venue.genres == [] or venue.genres == ['']):
                venue.genres = venue_info.get('genres')
                updated = True
                
            if venue_info.get('address') and (not venue.address or venue.address == ''):
                venue.address = venue_info.get('address')
                updated = True
                
            if venue_info.get('website_url') and (not venue.website_url or venue.website_url == ''):
                venue.website_url = venue_info.get('website_url')
                updated = True
                
            if updated:
                session.commit()
        
        return venue
    except Exception as e:
        logging.error(f"Error in get_or_create_venue for {venue_info['name']}: {e}")
        session.rollback()
        raise
    finally:
        # Close the session if we created it here
        if session_created:
            session.close()

def check_existing_concerts(session, venue_name):
    """Check if venue has any upcoming concerts"""
    # If session is None, create a new one
    session_created = False
    if session is None:
        session = Session()
        session_created = True
    
    try:
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
    except Exception as e:
        logging.error(f"Error in check_existing_concerts for {venue_name}: {e}")
        return []
    finally:
        # Close the session if we created it here
        if session_created:
            session.close()

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
    """Use a custom scraper for a specific venue"""
    try:
        if venue_name == 'Village Vanguard':
            from vanguard_scraper import scrape_vanguard
            return scrape_vanguard()
        elif venue_name == 'Close Up':
            from closeup_scraper import scrape_closeup
            return scrape_closeup()
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
        elif venue_name == 'Film at Lincoln Center':
            from lincoln_scraper import scrape_lincoln
            return scrape_lincoln()
        elif 'ra.co' in venue_url:
            from ra_scraper import scrape_ra
            return scrape_ra(venue_url)
    except Exception as e:
        logging.error(f"Error using custom scraper for {venue_name}: {e}")
        return []

def update_venue_data():
    """Utility function to ensure all venues have appropriate data"""
    db = SessionLocal()
    try:
        # Define known neighborhoods for venues (from migrations/add_venue_fields.py)
        venue_data = {
            'Village Vanguard': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
            'Smalls Jazz Club': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
            'Dizzy\'s Club': {'neighborhood': 'Columbus Circle', 'genres': ['Jazz']},
            'Mezzrow Jazz Club': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
            'The Jazz Gallery': {'neighborhood': 'Flatiron', 'genres': ['Jazz']},
            'Ornithology Cafe': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
            'Ornithology Jazz Club': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
            'Bar LunÀtico': {'neighborhood': 'Bedford-Stuyvesant', 'genres': ['Jazz']},
            'Bar Bayeux': {'neighborhood': 'Prospect Heights', 'genres': ['Jazz']},
            'The Owl Music Parlor': {'neighborhood': 'Prospect Heights', 'genres': ['Jazz']},
            'Marians Jazz Room': {'neighborhood': 'Williamsburg', 'genres': ['Jazz']},
            'Zinc Bar': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
            'The Stone': {'neighborhood': 'East Village', 'genres': ['Jazz']},
            'Nublu 151': {'neighborhood': 'East Village', 'genres': ['Jazz']},
            'Birdland': {'neighborhood': 'Theater District', 'genres': ['Jazz']},
            'Room 623 at B2 Harlem': {'neighborhood': 'Harlem', 'genres': ['Jazz']},
            'Smoke Jazz & Supper Club': {'neighborhood': 'Upper West Side', 'genres': ['Jazz']},
            'Drom': {'neighborhood': 'East Village', 'genres': ['Jazz']},
            'Roulette': {'neighborhood': 'Downtown Brooklyn', 'genres': ['Jazz']},
            'The Django': {'neighborhood': 'Tribeca', 'genres': ['Jazz']},
            'Joe\'s Pub': {'neighborhood': 'NoHo', 'genres': ['Jazz']},
            'Minton\'s Playhouse': {'neighborhood': 'Harlem', 'genres': ['Jazz']},
            'National Sawdust': {'neighborhood': 'Williamsburg', 'genres': ['Jazz']},
            'The Cutting Room': {'neighborhood': 'Flatiron', 'genres': ['Jazz']},
            'Symphony Space': {'neighborhood': 'Upper West Side', 'genres': ['Jazz']},
            'Le Poisson Rouge': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
            'Knockdown Center': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'Bossa Nova Civic Club': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'House of Yes': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'Jupiter Disco': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'Public Records': {'neighborhood': 'Gowanus', 'genres': ['Clubs']},
            'The Sultan Room': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'Mansions': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
            'Close Up': {'neighborhood': 'Lower East Side', 'genres': ['Jazz']},
            'IFC Center': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
            'Film Forum': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
            'Quad Cinema': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
            'Film at Lincoln Center': {'neighborhood': 'Upper West Side', 'genres': ['Movies']}
        }
        
        # Update venues with missing data
        venues = db.query(Venue).all()
        updated_count = 0
        
        for venue in venues:
            if venue.name in venue_data:
                data = venue_data[venue.name]
                updated = False
                
                if not venue.neighborhood and data.get('neighborhood'):
                    venue.neighborhood = data['neighborhood']
                    updated = True
                    
                if (not venue.genres or venue.genres == []) and data.get('genres'):
                    venue.genres = data['genres']
                    updated = True
                    
                if updated:
                    updated_count += 1
                    
        if updated_count > 0:
            db.commit()
            print(f"Updated data for {updated_count} venues")
        else:
            print("No venues needed updates")
            
    except Exception as e:
        print(f"Error updating venue data: {e}")
        db.rollback()
    finally:
        db.close()

def reset_database():
    """Reset database tables - handles both SQLite and PostgreSQL"""
    from config import DATABASE_URL
    from database import is_postgres
    
    if is_postgres:
        # For PostgreSQL, drop and recreate all tables using SQLAlchemy
        print("Dropping all tables in PostgreSQL database...")
        from base import Base
        Base.metadata.drop_all(bind=engine)
        print("Tables dropped, they will be recreated at next startup")
    else:
        # For SQLite, simply delete the database file
        db_path = "concerts.db"  # SQLite database path
        if os.path.exists(db_path):
            print(f"Deleting existing SQLite database at {db_path}")
            os.remove(db_path)
            print("Database file deleted, will be recreated")
        else:
            print("No SQLite database file found to delete")

if __name__ == '__main__':
    import sys
    from werkzeug.serving import run_simple
    from werkzeug.middleware.proxy_fix import ProxyFix
    
    if "--reset-db" in sys.argv or os.environ.get("RESET_DATABASE") == "true":
        reset_database()
    
    # Only run scraper in the main process, not in the reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        print("Starting in reloader process - skipping scraper")
    else:
        # Kill any existing scrapers first
        kill_existing_scrapers()
        
        # Update venue data to ensure neighborhoods and genres are set correctly
        update_venue_data()
        
        # Initialize based on arguments
        init_db()
        
        # Parse command line arguments
        run_scraper = True
        if len(sys.argv) > 1:
            if "no-scrape" in sys.argv:
                run_scraper = False
                logging.info("Starting web server without scraper")
            elif "server" in sys.argv:
                logging.info("Starting web server with scraper")
        
        if run_scraper:
            # Kill scrapers again just to be sure
            kill_existing_scrapers()
            scraper_thread = start_scraper_thread()
            atexit.register(lambda: scraper_thread.join(timeout=1.0))
    
    # Wrap the app to fix protocol headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    
    # Run with SSL
    run_simple('0.0.0.0', 5000, app,
               use_reloader=True,
               use_debugger=True,
               use_evalex=True,
               threaded=True)
