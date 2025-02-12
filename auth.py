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
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope='user-library-read playlist-modify-public user-read-email',
        show_dialog=True
    )

@auth.route('/login')
def login():
    """Redirect to Spotify login"""
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@auth.route('/callback')
def callback():
    """Handle Spotify OAuth callback"""
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    
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