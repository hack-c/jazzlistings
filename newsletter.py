from datetime import datetime, timedelta
import pytz
from sqlalchemy import and_
from models import User, Concert, Venue, Artist
from database import SessionLocal
import os
from openai import OpenAI
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from twilio.rest import Client

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

class NewsletterManager:
    def __init__(self):
        self.twilio_client = Client(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')

    def get_concerts_for_period(self, user, period='weekly'):
        """Get concerts based on frequency period"""
        db = SessionLocal()
        try:
            eastern = pytz.timezone('America/New_York')
            now = datetime.now(eastern)
            
            # Set end date based on frequency
            if period == 'daily':
                period_end = now + timedelta(days=1)
            else:  # weekly - show next 7 days from Sunday
                # If it's Sunday, show the full week ahead
                # If it's another day, show through next Sunday
                days_until_next_sunday = (7 - now.weekday()) % 7
                if days_until_next_sunday == 0:  # It's Sunday
                    period_end = now + timedelta(days=7)
                else:
                    period_end = now + timedelta(days=days_until_next_sunday)

            query = db.query(Concert).join(Venue).join(Concert.artists)

            # Apply user preferences
            if user.preferred_venues:
                query = query.filter(Concert.venue_id.in_(user.preferred_venues))
            if user.preferred_neighborhoods:
                query = query.filter(Venue.neighborhood.in_(user.preferred_neighborhoods))
            if user.preferred_genres:
                query = query.filter(Venue.genres.overlap(user.preferred_genres))

            concerts = query.filter(
                and_(
                    Concert.date >= now.date(),
                    Concert.date <= period_end.date()
                )
            ).all()

            return concerts
        finally:
            db.close()

    def generate_newsletter_content(self, user, concerts):
        """Generate personalized newsletter content using GPT-4"""
        # Create concert descriptions
        concert_descriptions = []
        for concert in concerts:
            artists = ", ".join([artist.name for artist in concert.artists])
            times = ", ".join([t.time.strftime("%I:%M %p") for t in concert.times])
            desc = f"{artists} at {concert.venue.name} on {concert.date.strftime('%A, %B %d')} at {times}"
            if concert.special_notes:
                desc += f" - {concert.special_notes}"
            concert_descriptions.append(desc)

        # Create prompt for GPT-4
        prompt = f"""You are a knowledgeable concert curator writing a personalized newsletter.
User preferences:
- Preferred venues: {[v.name for v in user.preferred_venues] if user.preferred_venues else 'All'}
- Preferred neighborhoods: {user.preferred_neighborhoods if user.preferred_neighborhoods else 'All'}
- Preferred genres: {user.preferred_genres if user.preferred_genres else 'All'}

Upcoming concerts this week:
{'\n'.join(concert_descriptions)}

Write a friendly, personalized newsletter highlighting the most relevant concerts for this user.
Focus on their preferences and include any special notes or recommendations.
Keep it concise but engaging."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a knowledgeable concert curator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error generating newsletter content: {e}")
            return self._generate_fallback_content(concerts)

    def _generate_fallback_content(self, concerts):
        """Generate basic newsletter content without AI"""
        content = ["Here are your upcoming concerts for the week:"]
        for concert in concerts:
            artists = ", ".join([artist.name for artist in concert.artists])
            times = ", ".join([t.time.strftime("%I:%M %p") for t in concert.times])
            content.append(f"\n{artists} at {concert.venue.name}")
            content.append(f"Date: {concert.date.strftime('%A, %B %d')} at {times}")
            if concert.special_notes:
                content.append(f"Note: {concert.special_notes}")
        return "\n".join(content)

    def send_email_newsletter(self, user, content):
        """Send newsletter via email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = user.email
            msg['Subject'] = "Your Weekly Concert Newsletter"
            msg.attach(MIMEText(content, 'plain'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            logging.info(f"Email newsletter sent to {user.email}")
            return True
        except Exception as e:
            logging.error(f"Error sending email newsletter: {e}")
            return False

    def send_sms_newsletter(self, user, content):
        """Send newsletter via SMS"""
        try:
            # Split content into smaller chunks if needed (SMS length limit)
            chunks = [content[i:i+1600] for i in range(0, len(content), 1600)]
            for chunk in chunks:
                self.twilio_client.messages.create(
                    body=chunk,
                    from_=os.getenv('TWILIO_PHONE_NUMBER'),
                    to=user.phone_number
                )
            logging.info(f"SMS newsletter sent to {user.phone_number}")
            return True
        except Exception as e:
            logging.error(f"Error sending SMS newsletter: {e}")
            return False

    def send_newsletters(self):
        """Send newsletters to users based on their preferred frequency"""
        db = SessionLocal()
        try:
            # Get current time in Eastern timezone
            eastern = pytz.timezone('America/New_York')
            now = datetime.now(eastern)
            
            # Get all subscribed users
            users = db.query(User).filter_by(newsletter_enabled=True).all()
            
            for user in users:
                # Skip if user has received newsletter too recently
                if user.last_newsletter:
                    last_newsletter = user.last_newsletter.replace(tzinfo=pytz.UTC).astimezone(eastern)
                    
                    # Check based on frequency
                    if user.newsletter_frequency == 'daily':
                        if now - last_newsletter < timedelta(hours=20):  # Allow 4-hour buffer
                            continue
                    else:  # weekly
                        if now - last_newsletter < timedelta(days=6):  # Allow 1-day buffer
                            continue
                
                # Get concerts for the user's preferred period
                concerts = self.get_concerts_for_period(user, user.newsletter_frequency)
                
                if concerts:
                    content = self.generate_newsletter_content(user, concerts)
                    success = False
                    
                    if user.email:
                        success = self.send_email_newsletter(user, content)
                    if user.phone_number:
                        success = self.send_sms_newsletter(user, content)
                        
                    if success:
                        # Update last newsletter timestamp
                        user.last_newsletter = now
                        db.commit()
        finally:
            db.close() 