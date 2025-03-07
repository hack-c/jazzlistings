# newsletter.py
import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import or_
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType
from jinja2 import Environment, FileSystemLoader
from models import User, Concert, Venue, ConcertTime
from database import SessionLocal
import pytz

# Initialize Jinja2 environment for email templates
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
jinja_env = Environment(loader=FileSystemLoader(templates_dir))

# Configure logger
logger = logging.getLogger('newsletter')
logger.setLevel(logging.INFO)

def should_send_newsletter(user):
    """
    Determine if a newsletter should be sent to the user based on their preferences
    and when they last received a newsletter.
    """
    if not user.newsletter_subscribed:
        return False
        
    # Get the current time in Eastern timezone
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    
    # If user has never received a newsletter, send one
    if not user.last_newsletter_sent:
        return True
        
    # Convert last_newsletter_sent to Eastern timezone for comparison
    if user.last_newsletter_sent.tzinfo is None:
        last_sent = user.last_newsletter_sent.replace(tzinfo=pytz.UTC).astimezone(eastern)
    else:
        last_sent = user.last_newsletter_sent.astimezone(eastern)
    
    # Check based on frequency preference
    if user.newsletter_frequency == 'daily':
        # Send if it's been more than 20 hours since the last newsletter
        # This allows for some wiggle room in the scheduling
        return (now - last_sent) > timedelta(hours=20)
    elif user.newsletter_frequency == 'weekly':
        # Send if it's been more than 6 days since the last newsletter
        return (now - last_sent) > timedelta(days=6)
    elif user.newsletter_frequency == 'biweekly':
        # Send if it's been more than 13 days
        return (now - last_sent) > timedelta(days=13)
    elif user.newsletter_frequency == 'monthly':
        # Send if it's been more than 27 days
        return (now - last_sent) > timedelta(days=27)
        
    # Default: don't send
    return False

def get_upcoming_events_for_user(user, days=None):
    """
    Get upcoming events based on user preferences and newsletter frequency.
    
    Args:
        user: The user to get events for
        days: Number of days to look ahead (overrides automatic calculation based on frequency)
    """
    # Determine number of days to look ahead based on frequency if not specified
    if days is None:
        if user.newsletter_frequency == 'daily':
            days = 7  # Daily newsletters show the next 7 days
        else:
            days = 14  # Weekly/biweekly/monthly show next 2 weeks
    db = SessionLocal()
    try:
        # Use Eastern timezone for date comparisons
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        today = now.date()
        end_date = today + timedelta(days=days)
        
        # Base query with joins
        query = (
            db.query(Concert)
            .join(Venue)
            .outerjoin(ConcertTime)
        )
        
        # Apply preference filters if user has preferences
        if user.preferred_venues or user.preferred_neighborhoods or user.preferred_genres:
            # Create a list to collect filter conditions
            filter_conditions = []
            
            # For each preference type, add a condition
            if user.preferred_venues:
                filter_conditions.append(Concert.venue_id.in_(user.preferred_venues))
                
            if user.preferred_neighborhoods:
                filter_conditions.append(Venue.neighborhood.in_(user.preferred_neighborhoods))
                
            if user.preferred_genres:
                # For each preferred genre, check if it's in the venue's genre list
                genre_conditions = []
                for genre in user.preferred_genres:
                    # This properly checks if a single genre is in the JSON array
                    genre_conditions.append(Venue.genres.cast(str).like(f'%"{genre}"%'))
                
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
            Concert.date <= end_date
        )
        
        # Get all concerts with related data
        concerts = query.all()
        
        # Return events with their venue information
        events = []
        for concert in concerts:
            events.append({
                'id': concert.id,
                'date': concert.date,
                'venue': concert.venue.name,
                'artists': [artist.name for artist in concert.artists],
                'times': [t.time.strftime('%I:%M %p') if t.time else '8:00 PM' for t in concert.times],
                'ticket_link': concert.ticket_link,
                'price_range': concert.price_range,
                'special_notes': concert.special_notes,
                'neighborhood': concert.venue.neighborhood
            })
        
        # Sort by date
        events.sort(key=lambda x: x['date'])
        
        # Group events by date and neighborhood
        grouped_events = {}
        for event in events:
            date_key = event['date']
            if date_key not in grouped_events:
                grouped_events[date_key] = {}
            
            neighborhood = event['neighborhood'] or 'Other'
            if neighborhood not in grouped_events[date_key]:
                grouped_events[date_key][neighborhood] = []
            
            grouped_events[date_key][neighborhood].append(event)
            
        return grouped_events
    finally:
        db.close()

def generate_newsletter_html(user, events):
    """
    Generate HTML content for the email newsletter
    """
    template = jinja_env.get_template('email.html')
    return template.render(
        user_email=user.email,
        events=events,
        frequency=user.newsletter_frequency.capitalize()
    )

def send_newsletter(user, html_content):
    """
    Send newsletter email to a user using SendGrid
    """
    try:
        # Get SendGrid API key from environment
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            logger.error("SendGrid API key not found. Unable to send newsletter.")
            return False
            
        # Create email
        from_email = Email(os.environ.get('FROM_EMAIL', 'noreply@yourconcertapp.com'))
        to_email = To(user.email)
        subject = "Your Personalized Concert Listings"
        content = Content(MimeType.html, html_content)
        
        mail = Mail(from_email, to_email, subject, content)
        
        # Send email
        sg = SendGridAPIClient(api_key)
        response = sg.send(mail)
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Newsletter sent successfully to {user.email}")
            return True
        else:
            logger.error(f"Failed to send newsletter to {user.email}. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending newsletter to {user.email}: {str(e)}")
        return False

def process_newsletters(force=False):
    """
    Process newsletters for all subscribed users
    
    Args:
        force (bool): If True, will send newsletters regardless of timing rules
    """
    db = SessionLocal()
    try:
        # Get all active users who are subscribed to the newsletter
        users = db.query(User).filter(
            User.is_active == True,
            User.newsletter_subscribed == True
        ).all()
        
        logger.info(f"Processing newsletters for {len(users)} subscribed users (force={force})")
        
        for user in users:
            try:
                # Check if we should send newsletter based on frequency (unless force=True)
                if force or should_send_newsletter(user):
                    # Get upcoming events for user based on their newsletter frequency
                    # Daily users get 3 days ahead, others get 14 days ahead
                    events = get_upcoming_events_for_user(user)
                    
                    # Only send if there are events to share
                    if events:
                        # Generate newsletter content
                        html_content = generate_newsletter_html(user, events)
                        
                        # Send newsletter
                        if send_newsletter(user, html_content):
                            # Update last sent timestamp
                            user.last_newsletter_sent = datetime.now(pytz.UTC)
                            db.commit()
                            logger.info(f"Newsletter sent to {user.email}")
                    else:
                        logger.info(f"No events to send to {user.email}")
                else:
                    logger.info(f"Skipping newsletter for {user.email} (not due yet)")
            except Exception as e:
                logger.error(f"Error processing newsletter for {user.email}: {str(e)}")
                db.rollback()
        
    except Exception as e:
        logger.error(f"Error in process_newsletters: {str(e)}")
    finally:
        db.close()

def schedule_newsletters():
    """
    Schedule newsletters to run every day
    """
    import schedule
    
    # Function to process only daily newsletters
    def process_daily_newsletters():
        db = SessionLocal()
        try:
            # Get users subscribed to daily newsletters
            users = db.query(User).filter(
                User.is_active == True,
                User.newsletter_subscribed == True,
                User.newsletter_frequency == 'daily'
            ).all()
            
            if not users:
                logger.info("No users subscribed to daily newsletters")
                return
                
            logger.info(f"Processing daily newsletters for {len(users)} users")
            for user in users:
                try:
                    # Check timing
                    if should_send_newsletter(user):
                        # Get upcoming events for next 7 days
                        events = get_upcoming_events_for_user(user, days=7)
                        
                        # Only send if there are events to share
                        if events:
                            # Generate newsletter content
                            html_content = generate_newsletter_html(user, events)
                            
                            # Send newsletter
                            if send_newsletter(user, html_content):
                                # Update last sent timestamp
                                user.last_newsletter_sent = datetime.now(pytz.UTC)
                                db.commit()
                                logger.info(f"Daily newsletter sent to {user.email}")
                        else:
                            logger.info(f"No events in next 7 days for {user.email}")
                    else:
                        logger.info(f"Skipping daily newsletter for {user.email} (not due yet)")
                except Exception as e:
                    logger.error(f"Error processing daily newsletter for {user.email}: {str(e)}")
                    db.rollback()
        except Exception as e:
            logger.error(f"Error processing daily newsletters: {str(e)}")
        finally:
            db.close()
    
    # Function to process weekly/biweekly/monthly newsletters
    def process_regular_newsletters():
        db = SessionLocal()
        try:
            # Get users not subscribed to daily newsletters
            users = db.query(User).filter(
                User.is_active == True,
                User.newsletter_subscribed == True,
                User.newsletter_frequency != 'daily'
            ).all()
            
            if not users:
                logger.info("No users subscribed to weekly/biweekly/monthly newsletters")
                return
                
            logger.info(f"Processing regular newsletters for {len(users)} users")
            for user in users:
                try:
                    # Check timing
                    if should_send_newsletter(user):
                        # Get upcoming events for user (defaults to 14 days)
                        events = get_upcoming_events_for_user(user)
                        
                        # Only send if there are events to share
                        if events:
                            # Generate newsletter content
                            html_content = generate_newsletter_html(user, events)
                            
                            # Send newsletter
                            if send_newsletter(user, html_content):
                                # Update last sent timestamp
                                user.last_newsletter_sent = datetime.now(pytz.UTC)
                                db.commit()
                                logger.info(f"Regular newsletter sent to {user.email}")
                        else:
                            logger.info(f"No events to send to {user.email}")
                    else:
                        logger.info(f"Skipping newsletter for {user.email} (not due yet)")
                except Exception as e:
                    logger.error(f"Error processing newsletter for {user.email}: {str(e)}")
                    db.rollback()
        except Exception as e:
            logger.error(f"Error processing regular newsletters: {str(e)}")
        finally:
            db.close()
    
    # Run daily newsletters at 7 AM Eastern every day
    schedule.every().day.at("07:00").do(process_daily_newsletters)
    
    # Run weekly/biweekly/monthly newsletters on Sunday at 8 AM Eastern
    schedule.every().sunday.at("08:00").do(process_regular_newsletters)
    
    logger.info("Newsletter scheduler initialized")