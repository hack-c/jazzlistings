from flask import Blueprint, session, redirect, url_for, request, flash
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from models import User
from database import SessionLocal
import logging
import json

logger = logging.getLogger('concert_app')

google_auth = Blueprint('google_auth', __name__)

# Set up OAuth 2.0 credentials
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
# Make sure the Google redirect URI includes the /google prefix
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/google/callback')

# Scopes to request
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

def get_google_flow():
    """Create and return a Google OAuth flow object"""
    logger.info("Initializing Google OAuth flow")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow

@google_auth.route('/login')
def login():
    """Redirect to Google login"""
    try:
        flow = get_google_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Store the state in the session for later verification
        session['google_state'] = state
        
        logger.info(f"Redirecting to Google auth URL: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Error in Google login route: {str(e)}")
        flash(f"Error authenticating with Google: {str(e)}")
        return redirect(url_for('index'))

@google_auth.route('/callback')
def callback():
    """Handle Google OAuth callback"""
    logger.info(f"Google callback received with args: {request.args}")
    
    # Check for error
    if request.args.get('error'):
        flash(f"Google authentication failed: {request.args.get('error')}")
        return redirect(url_for('index'))
    
    # Get the state from the request
    state = request.args.get('state')
    stored_state = session.get('google_state')
    
    # Verify state
    logger.info(f"Checking state: received={state}, stored={stored_state}")
    if not state or state != stored_state:
        logger.error("State mismatch in Google callback")
        flash("State verification failed. Please try again.")
        return redirect(url_for('index'))
    
    try:
        flow = get_google_flow()
        # Set the state on the flow object to match the state from the request
        # This is important for the OAuth2 validation to work correctly
        flow.state = state
        flow.fetch_token(authorization_response=request.url)
        
        credentials = flow.credentials
        
        # Get user info from Google
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        
        email = user_info.get('email')
        if not email:
            logger.error("No email returned from Google")
            flash("Failed to get email from Google. Please try again.")
            return redirect(url_for('index'))
        
        # Store token info
        token_info = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        db = SessionLocal()
        try:
            # Check if user already exists with this email
            user = db.query(User).filter_by(email=email).first()
            
            if not user:
                # Create new user
                user = User(
                    email=email,
                    google_token=token_info,  # Store Google token instead of Spotify token
                    is_active=True
                )
                db.add(user)
                db.commit()
                logger.info(f"Created new user with Google auth: {email}")
            else:
                # Update existing user
                user.google_token = token_info
                db.commit()
                logger.info(f"Updated existing user with Google auth: {email}")
            
            session['user_id'] = user.id
            flash('Successfully logged in with Google!')
        finally:
            db.close()
        
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in Google callback: {str(e)}")
        flash(f"Error processing Google login: {str(e)}")
        return redirect(url_for('index'))