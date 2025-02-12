from flask import Blueprint, session, redirect, url_for, request, flash, render_template
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from models import User
from database import SessionLocal

auth = Blueprint('auth', __name__)

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')

def create_spotify_oauth():
    oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope='user-library-read playlist-modify-public user-read-email',
        show_dialog=True,
        cache_handler=None  # Disable caching to avoid issues
    )
    print(f"OAuth created with client_id: {SPOTIFY_CLIENT_ID[:5]}...")  # Debug print (only first 5 chars for security)
    print(f"Redirect URI set to: {SPOTIFY_REDIRECT_URI}")  # Debug print
    return oauth

@auth.route('/login')
def login():
    """Redirect to Spotify login"""
    try:
        print("\nSpotify OAuth Debug Info:")
        print(f"Client ID: {SPOTIFY_CLIENT_ID[:5]}...")
        print(f"Redirect URI: {SPOTIFY_REDIRECT_URI}")
        print(f"Current request URL: {request.url}")
        print(f"Current request base URL: {request.base_url}")
        
        sp_oauth = create_spotify_oauth()
        auth_url = sp_oauth.get_authorize_url()
        print(f"Generated Auth URL: {auth_url}\n")
        return redirect(auth_url)
    except Exception as e:
        print(f"Error in login route: {str(e)}")
        return f"Error: {str(e)}", 500

@auth.route('/callback')
def callback():
    """Handle Spotify OAuth callback"""
    print("\nCallback Debug Info:")
    print(f"Request URL: {request.url}")
    print(f"Request Base URL: {request.base_url}")
    print(f"Request Host: {request.host}")
    print(f"Configured Redirect URI: {SPOTIFY_REDIRECT_URI}")
    print(f"Request Args: {request.args}")
    
    print(f"Callback received with args: {request.args}")
    print(f"Full request URL: {request.url}")
    print("Callback received!")  # Debug print
    print(f"Request args: {request.args}")  # Debug print
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')
    if not code:
        print("No code received in callback")  # Debug print
        flash('Authentication failed')
        return redirect(url_for('index'))
    
    try:
        token_info = sp_oauth.get_access_token(code)
        print("Token received successfully")  # Debug print
    except Exception as e:
        print(f"Error getting token: {e}")  # Debug print
        flash('Authentication failed')
        return redirect(url_for('index'))
    
    # Get user info from Spotify
    sp = spotipy.Spotify(auth=token_info['access_token'])
    spotify_user = sp.current_user()
    email = spotify_user['email']
    
    db = SessionLocal()
    try:
        # Find or create user
        user = db.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                spotify_token=token_info,
                is_active=True
            )
            db.add(user)
            db.commit()
        else:
            user.spotify_token = token_info
            db.commit()
        
        session['user_id'] = user.id
        flash('Successfully logged in with Spotify!')
    finally:
        db.close()
    
    return redirect(url_for('index'))

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index')) 