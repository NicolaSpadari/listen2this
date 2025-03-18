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

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
SPOTIPY_REFRESH_TOKEN = os.environ.get('SPOTIPY_REFRESH_TOKEN')
REDDIT_USER_AGENT = 'Listen2This v1.0'

def get_reddit_posts(subreddit, time_filter='month', limit=20):
    headers = {'User-Agent': REDDIT_USER_AGENT}
    url = f'https://www.reddit.com/r/{subreddit}/top.json?t={time_filter}&limit={limit}'
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['data']['children']
    else:
        print(f"Error fetching Reddit data: {response.status_code}")
        return []

def parse_song_titles(posts):
    songs = []
    for post in posts:
        title = post['data']['title']
        
        # Post format: "Artist -/—/--/ Title [genre] (year)"
        if " -- " in title:
            artist, rest = title.split(" -- ", 1)
        elif " - " in title:
            artist, rest = title.split(" - ", 1)
        elif " — " in title:
            artist, rest = title.split(" — ", 1)
            
        song_title = rest.split('[', 1)[0].split('(', 1)[0].strip()
        songs.append({
            'artist': artist.strip(),
            'title': song_title,
            'query': f"{artist} {song_title}"
        })
    return songs

def get_spotify_client():
    scope="ugc-image-upload user-library-read user-read-private user-read-email playlist-modify-public playlist-modify-private"
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, open_browser=False))    
    return sp

def create_spotify_playlist(songs):
    sp = get_spotify_client()
    user_id = sp.current_user()['id']
    
    current_year = date.today().year
    current_month = date.today().month
    playlist_name = f"r/listentothis {current_month}/{current_year}"
    
    playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=True,
        description=f"Top tracks from r/listentothis for {current_month}/{current_year}"
    )
    
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
        sp.playlist_add_items(playlist['id'], track_ids)
        print(f"Added {len(track_ids)} tracks to playlist")
    
    if not_found:
        print(f"Could not find {len(not_found)} tracks on Spotify:")
        for song in not_found:
            print(f"  - {song['artist']} - {song['title']}")
    
    return playlist

def get_and_modify_cover_image():
    posts = get_reddit_posts('earthporn', limit=1)
    if not posts:
        return None
    
    image_url = posts[0]['data']['url']
    response = requests.get(image_url)
    if response.status_code != 200:
        print(f"Error downloading image: {response.status_code}")
        return None
    
    image = Image.open(io.BytesIO(response.content))
    print(f"Original image size: {image.size}")
    
    # Resize to max 500px for height/width
    max_size = 500
    image.thumbnail((max_size, max_size), Image.LANCZOS)
    print(f"Resized image size: {image.size}")
    
    # Crop to square
    width, height = image.size
    crop_size = min(width, height)
    left = (width - crop_size) // 2
    top = (height - crop_size) // 2
    right = left + crop_size
    bottom = top + crop_size
    image = image.crop((left, top, right, bottom))
    print(f"Cropped image size: {image.size}")
    
    # Add text
    draw = ImageDraw.Draw(image)
    current_month = date.today().strftime("%B")
    font_path = os.path.join(os.path.dirname(__file__), "inter.ttf")
    font = ImageFont.truetype(font_path, 40)
    
    text_bbox = draw.textbbox((0, 0), current_month, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    position = (image.width - text_width - 20, image.height - text_height - 20)
    
    shadow_offset = 2
    shadow_position = (position[0] + shadow_offset, position[1] + shadow_offset)
    draw.text(shadow_position, current_month, font=font, fill=(0, 0, 0, 180))
    draw.text(position, current_month, font=font, fill=(255, 255, 255, 230))
    
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=85)
    img_byte_arr.seek(0)
    
    print(f"Final image size: {len(img_byte_arr.getvalue()) / 1024:.2f} KB")
    
    return img_byte_arr

def set_playlist_cover(playlist_id, image_data):
    sp = get_spotify_client()
    
    try:
        b64_image = base64.b64encode(image_data.read()).decode('utf-8')
        sp.playlist_upload_cover_image(playlist_id, b64_image)
        print("Successfully updated playlist cover image")
        return True
    except Exception as e:
        print(f"Error uploading cover image: {e}")
        return False

def create_monthly_playlist():
    print(f"Starting playlist creation for {datetime.now().strftime('%B %Y')}...")
    
    posts = get_reddit_posts('listentothis', limit=20)
    if not posts:
        print("No posts found from r/listentothis, exiting")
        return
    
    songs = parse_song_titles(posts)
    
    if not songs:
        print("No valid song titles found, exiting")
        return
    
    print(f"Found {len(songs)} songs")
    
    playlist = create_spotify_playlist(songs)
    image_data = get_and_modify_cover_image()
    
    if image_data and playlist:
        set_playlist_cover(playlist['id'], image_data)
        
    print("Playlist created")

if __name__ == "__main__":
    if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI]):
        print("Missing environment variables")
    else:
        create_monthly_playlist()