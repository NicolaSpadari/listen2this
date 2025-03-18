#!/usr/bin/env python3
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, date
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PIL import Image, ImageDraw, ImageFont
import io
import base64

load_dotenv()

# Environment variables for authentication
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
SPOTIPY_REFRESH_TOKEN = os.environ.get('SPOTIPY_REFRESH_TOKEN')
REDDIT_USER_AGENT = 'Monthly Playlist Creator v1.0'

def get_reddit_posts(subreddit, time_filter='month', limit=20):
    """Get top posts from a subreddit."""
    headers = {'User-Agent': REDDIT_USER_AGENT}
    url = f'https://www.reddit.com/r/{subreddit}/top.json?t={time_filter}&limit={limit}'
    
    print(f"Fetching data from {url}")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['data']['children']
    else:
        print(f"Error fetching Reddit data: {response.status_code}")
        return []

def parse_song_titles(posts):
    """Extract artist and song title from post titles."""
    songs = []
    for post in posts:
        title = post['data']['title']
        # Common format: "Artist - Title [genre] (year)"
        if ' - ' in title:
            artist, rest = title.split(' - ', 1)
            # Further extract the song title (before any brackets/parentheses)
            song_title = rest.split('[', 1)[0].split('(', 1)[0].strip()
            songs.append({
                'artist': artist.strip(),
                'title': song_title,
                'query': f"{artist} {song_title}"
            })
    print(songs)
    return songs

def get_spotify_client():
    """Get authenticated Spotify client using refresh token for Docker environments."""
    scope="ugc-image-upload user-library-read user-read-private user-read-email playlist-modify-public playlist-modify-private"
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, open_browser=False))
    
    return sp

def create_spotify_playlist(songs):
    """Create a Spotify playlist with the given songs."""
    # Get authenticated client
    sp = get_spotify_client()
    
    # Get current user
    user_id = sp.current_user()['id']
    print(f"Creating playlist for user {user_id}")
    
    # Create new playlist
    current_year = date.today().year
    current_month = date.today().month
    playlist_name = f"r/listentothis {current_month}/{current_year}"
    
    playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=True,
        description=f"Top tracks from r/listentothis for {current_month}/{current_year}."
    )
    
    # Search for songs and add to playlist
    track_ids = []
    not_found = []
    
    for song in songs:
        query = song['query']
        print(f"Searching for: {query}")
        result = sp.search(q=query, type='track', limit=1)
        
        if result['tracks']['items']:
            track = result['tracks']['items'][0]
            track_id = track['id']
            track_ids.append(track_id)
            print(f"Found: {track['artists'][0]['name']} - {track['name']}")
        else:
            not_found.append(song)
            print(f"Not found: {song['artist']} - {song['title']}")
    
    # Add tracks to playlist in batches (Spotify API limits)
    if track_ids:
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            sp.playlist_add_items(playlist['id'], batch)
            print(f"Added {len(batch)} tracks to playlist")
    
    if not_found:
        print(f"Could not find {len(not_found)} tracks on Spotify:")
        for song in not_found:
            print(f"  - {song['artist']} - {song['title']}")
    
    return playlist

def get_and_modify_cover_image():
    """Get top image from r/earthporn and add text."""
    posts = get_reddit_posts('earthporn', limit=1)
    if not posts:
        return None
    
    # Get image URL
    image_url = posts[0]['data']['url']
    print(f"Using image from: {image_url}")
    
    # Download image
    response = requests.get(image_url)
    if response.status_code != 200:
        print(f"Error downloading image: {response.status_code}")
        return None
    
    # Open image and add text
    image = Image.open(io.BytesIO(response.content))
    print(f"Image size: {image.size}")
    
    # Resize if necessary (Spotify requires 300x300 to 3000x3000)
    max_size = 1500
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.LANCZOS)
        print(f"Resized to: {new_size}")
    
    # Create draw object
    draw = ImageDraw.Draw(image)
    
    # Add text with month
    current_month = date.today().strftime("%B")
    
    # Try to use a nice font, fall back to default if not available
    try:
        # For Docker, use a more commonly available font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        print("Using DejaVu Sans Bold font")
    except IOError:
        try:
            font = ImageFont.truetype("Arial.ttf", 60)
            print("Using Arial font")
        except IOError:
            font = ImageFont.load_default()
            print("Using default font")
    
    # Calculate text position (bottom right corner with padding)
    try:
        # For newer Pillow versions
        text_bbox = draw.textbbox((0, 0), current_month, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        print("Using textbbox for text dimensions")
    except AttributeError:
        # For older Pillow versions
        text_width, text_height = draw.textsize(current_month, font=font)
        print("Using textsize for text dimensions")
    
    position = (image.width - text_width - 20, image.height - text_height - 20)
    
    # Add shadow for better visibility
    shadow_offset = 2
    shadow_position = (position[0] + shadow_offset, position[1] + shadow_offset)
    
    # Draw text with shadow
    try:
        # For newer Pillow versions
        draw.text(shadow_position, current_month, font=font, fill=(0, 0, 0, 180))
        draw.text(position, current_month, font=font, fill=(255, 255, 255, 230))
    except TypeError:
        # For older Pillow versions that don't support alpha in fill
        draw.text(shadow_position, current_month, font=font, fill=(0, 0, 0))
        draw.text(position, current_month, font=font, fill=(255, 255, 255))
    
    # Save to BytesIO object
    img_byte_arr = io.BytesIO()
    # Save with higher compression (lower quality)
    image.save(img_byte_arr, format='JPEG', quality=85)  # Reduce quality from default (95) to 85
    img_byte_arr.seek(0)
    
    # Add a check for file size
    file_size = len(img_byte_arr.getvalue()) / 1024  # Size in KB
    print(f"Image size: {file_size:.2f} KB")
    
    # If still too large, resize and compress further
    if file_size > 200:  # Spotify's limit is 256KB but leaving some margin
        # Try more aggressive compression first
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=70)
        img_byte_arr.seek(0)
        
        # If still too large, resize the image further
        if len(img_byte_arr.getvalue()) / 1024 > 200:
            # Reduce dimensions by 25%
            new_size = (int(image.width * 0.75), int(image.height * 0.75))
            image = image.resize(new_size, Image.LANCZOS)
            
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=70)
            img_byte_arr.seek(0)
            
        print(f"Compressed image size: {len(img_byte_arr.getvalue()) / 1024:.2f} KB")
    
    return img_byte_arr

def set_playlist_cover(playlist_id, image_data):
    """Set the playlist cover image."""
    sp = get_spotify_client()
    
    try:
        # Convert image data to base64 string
        b64_image = base64.b64encode(image_data.read()).decode('utf-8')
        sp.playlist_upload_cover_image(playlist_id, b64_image)
        print("Successfully updated playlist cover image")
        return True
    except Exception as e:
        print(f"Error uploading cover image: {e}")
        return False

def create_monthly_playlist():
    """Main function to create the monthly playlist."""
    print(f"Starting playlist creation for {datetime.now().strftime('%B %Y')}...")
    
    # Get top songs from r/listentothis
    posts = get_reddit_posts('listentothis')
    if not posts:
        print("No posts found from r/listentothis. Exiting.")
        return
    
    songs = parse_song_titles(posts)
    
    if not songs:
        print("No valid song titles found. Exiting.")
        return
    
    print(f"Found {len(songs)} songs")
    
    # Create Spotify playlist
    playlist = create_spotify_playlist(songs)
    
    # Get and modify cover image
    image_data = get_and_modify_cover_image()
    
    if image_data and playlist:
        # Set playlist cover
        set_playlist_cover(playlist['id'], image_data)
        
    print("Playlist creation complete!")

if __name__ == "__main__":
    if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI]):
        print("Error: Please set environment variables.")
    else:
        create_monthly_playlist()