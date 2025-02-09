from flask import Blueprint, session, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from models import User
from database import SessionLocal

auth = Blueprint('auth', __name__)

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope='user-library-read playlist-modify-public'
    )

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                return redirect(url_for('index'))
            flash('Please check your login details and try again.')
        finally:
            db.close()
    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(email=email).first()
            if user:
                flash('Email already exists')
                return redirect(url_for('auth.signup'))
            
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.add(new_user)
            db.commit()
            
            session['user_id'] = new_user.id
            return redirect(url_for('index'))
        finally:
            db.close()
    return render_template('signup.html')

@auth.route('/spotify-login')
def spotify_login():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@auth.route('/spotify-callback')
def spotify_callback():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        user.spotify_token = token_info
        db.commit()
        flash('Successfully connected to Spotify!')
    finally:
        db.close()
    
    return redirect(url_for('index'))

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index')) 