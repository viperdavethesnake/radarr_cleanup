#!/usr/bin/env python3

import os
import subprocess
import re
import requests
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

def search_tv_show(show_name):
    """Search for a TV show on TMDB"""
    url = f"{TMDB_BASE_URL}/search/tv"
    params = {
        'api_key': TMDB_API_KEY,
        'query': show_name,
        'language': 'en-US'
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            return results[0]  # Return the first (most relevant) result
    return None

def get_episode_info(show_id, season_num, episode_num):
    """Get episode information from TMDB"""
    url = f"{TMDB_BASE_URL}/tv/{show_id}/season/{season_num}/episode/{episode_num}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def strip_mkv_tags(mkv_file):
    """Strip all tags from MKV file"""
    try:
        cmd = ['mkvpropedit', '--tags', 'all:', mkv_file]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  ✅ Stripped tags from: {os.path.basename(mkv_file)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error stripping tags from {mkv_file}: {e}")
        return False

def add_episode_title(mkv_file, title):
    """Add episode title to MKV file"""
    try:
        cmd = ['mkvpropedit', '--set', f'title={title}', mkv_file]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  ✅ Added title '{title}' to: {os.path.basename(mkv_file)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error adding title to {mkv_file}: {e}")
        return False

def remux_clean(mkv_file):
    """Remux MKV file to remove unwanted tracks"""
    try:
        # Create temporary output file
        temp_output = mkv_file.replace('.mkv', '_temp.mkv')
        
        # Build mkvmerge command to keep only video and best English audio
        cmd = [
            'mkvmerge', '-o', temp_output,
            '--no-chapters', '--no-attachments',
            '--video-tracks', '0',
            '--language', '0:eng',
            '--audio-tracks', '1',  # Keep first audio track (usually best quality)
            '--language', '1:eng',
            '--no-subtitles',
            mkv_file
        ]
        
        print(f"  🔄 Remuxing: {os.path.basename(mkv_file)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Replace original with cleaned version
            os.replace(temp_output, mkv_file)
            print(f"  ✅ Remuxed: {os.path.basename(mkv_file)}")
            return True
        else:
            print(f"  ❌ Remux failed for {mkv_file}: {result.stderr}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
            
    except Exception as e:
        print(f"  ❌ Exception during remux: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False

def process_episode(mkv_file, show_data):
    """Process a single episode file"""
    filename = os.path.basename(mkv_file)
    
    # Extract episode info from filename: Glee_-_S01E01_-_Pilot.mkv
    match = re.match(r'(.+)_-_S(\d{2})E(\d{2})_-_(.+?)\.mkv', filename)
    if not match:
        print(f"  ❌ Could not parse filename: {filename}")
        return False
    
    show_name, season_num, episode_num, episode_title = match.groups()
    season_num = int(season_num)
    episode_num = int(episode_num)
    
    print(f"  📺 Processing: {filename}")
    
    # Step 1: Strip existing tags
    if not strip_mkv_tags(mkv_file):
        return False
    
    # Step 2: Add episode title
    clean_title = episode_title.replace('_', ' ')
    if not add_episode_title(mkv_file, clean_title):
        return False
    
    # Step 3: Remux to clean tracks
    if not remux_clean(mkv_file):
        return False
    
    return True

def process_show_folder(show_folder_path):
    """Process all episodes in a show folder"""
    show_name = os.path.basename(show_folder_path)
    print(f"\n🎬 Processing show: {show_name}")
    
    # Search for show on TMDB
    clean_show_name = show_name.replace('_', ' ').replace('(', '').replace(')', '')
    show_data = search_tv_show(clean_show_name)
    
    if not show_data:
        print(f"  ❌ Could not find show '{clean_show_name}' on TMDB")
        return False
    
    print(f"  ✅ Found TMDB ID: {show_data['id']}")
    
    # Process each season folder
    success_count = 0
    total_count = 0
    
    for season_folder in sorted(os.listdir(show_folder_path)):
        season_path = os.path.join(show_folder_path, season_folder)
        if not os.path.isdir(season_path) or not season_folder.startswith('Season_'):
            continue
        
        print(f"\n  📁 Processing {season_folder}...")
        
        for filename in sorted(os.listdir(season_path)):
            if not filename.endswith('.mkv'):
                continue
            
            total_count += 1
            mkv_file = os.path.join(season_path, filename)
            
            if process_episode(mkv_file, show_data):
                success_count += 1
    
    print(f"\n✅ Processed {show_name}: {success_count}/{total_count} episodes")
    return success_count == total_count

def main():
    """Main processing function"""
    print("🎬 TV Show In-Place Cleanup Script")
    print("=" * 50)
    
    # Check if TMDB API key is set
    if not TMDB_API_KEY or TMDB_API_KEY == "your_tmdb_api_key_here":
        print("❌ Please set your TMDB API key in the .env file")
        return
    
    # Process shows in tvshows directory
    tvshows_dir = "/storage/media/servarr/tvshows"
    
    if not os.path.exists(tvshows_dir):
        print(f"❌ Directory not found: {tvshows_dir}")
        return
    
    success_count = 0
    total_shows = 0
    
    for item in os.listdir(tvshows_dir):
        item_path = os.path.join(tvshows_dir, item)
        if os.path.isdir(item_path):
            total_shows += 1
            if process_show_folder(item_path):
                success_count += 1
    
    print(f"\n🎉 Processing complete: {success_count}/{total_shows} shows successful")
    print("\n✅ All files processed in-place - no copies created!")

if __name__ == "__main__":
    main() 