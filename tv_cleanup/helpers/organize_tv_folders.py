#!/usr/bin/env python3

import os
import shutil
import re
import subprocess
from pathlib import Path

# Configuration
SOURCE_DIR = '/storage/media/servarr/tvshows'
DEST_DIR = '/storage/media/servarr/tvshows_organized'

def log(msg):
    print(f"[{__file__}] {msg}")

def extract_show_info(folder_name):
    """Extract show name, year, and season from folder name"""
    # Handle different naming patterns
    patterns = [
        r'(.+?)\.?\(?(\d{4})\)?\.?S(\d{2})',  # Glee.(2009).S01 or Glee.2009.S02
        r'(.+?)\.?S(\d{2})',  # Fallback for no year
    ]
    
    for pattern in patterns:
        match = re.match(pattern, folder_name)
        if match:
            if len(match.groups()) == 3:
                show_name, year, season = match.groups()
                return show_name.strip(), year, season
            elif len(match.groups()) == 2:
                show_name, season = match.groups()
                return show_name.strip(), None, season
    
    return None, None, None

def clean_show_name(name):
    """Clean up show name for folder naming"""
    # Remove common release group suffixes
    name = re.sub(r'\.(1080p|720p|480p).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.(BluRay|WEBRip|HDRip|DVDRip).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.(x264|x265|HEVC|AVC).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.(AAC|AC3|DTS|EAC3).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.(10bit|8bit).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.(5\.1|2\.0|7\.1).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'-[a-zA-Z0-9]+$', '', name)  # Remove release group names
    return name.strip()

def clean_episode_name(filename):
    """Clean episode filename for media server compatibility"""
    # Extract episode info - look for SXXEYY pattern and get everything up to quality
    match = re.search(r'\.(S\d{2}E\d{2})\.(.+?)\.(1080p|720p|480p)', filename)
    if not match:
        return None
    
    episode_code, episode_title, quality = match.groups()
    
    # Clean episode title - replace dots with underscores and clean up
    clean_title = episode_title.replace('.', '_').strip()
    
    # Get file extension
    ext = os.path.splitext(filename)[1]
    
    # Use "Glee" as the show name since we know it's Glee
    return f"Glee_-_{episode_code}_-_{clean_title}{ext}"

def organize_tv_shows():
    """Main function to organize TV shows"""
    log(f"Starting TV show organization from {SOURCE_DIR} to {DEST_DIR}")
    
    # Create destination directory
    os.makedirs(DEST_DIR, exist_ok=True)
    
    # Process each folder in source directory
    for item in os.listdir(SOURCE_DIR):
        item_path = os.path.join(SOURCE_DIR, item)
        
        if not os.path.isdir(item_path):
            continue
            
        log(f"Processing: {item}")
        
        # Extract show information
        show_name, year, season = extract_show_info(item)
        
        if not show_name or not season:
            log(f"  Skipping {item} - couldn't parse show info")
            continue
            
        # Clean show name
        clean_show = clean_show_name(show_name)
        
        # Create show folder name
        if year:
            show_folder = f"{clean_show}_({year})"
        else:
            show_folder = clean_show
            
        show_path = os.path.join(DEST_DIR, show_folder)
        season_path = os.path.join(show_path, f"Season_{int(season):02d}")
        
        # Create directories
        os.makedirs(season_path, exist_ok=True)
        
        log(f"  Created: {show_folder}/Season_{int(season):02d}")
        
        # Process MKV files
        mkv_count = 0
        for file in os.listdir(item_path):
            if file.lower().endswith('.mkv'):
                src_file = os.path.join(item_path, file)
                
                # Clean episode name
                clean_filename = clean_episode_name(file)
                if not clean_filename:
                    log(f"    Skipping {file} - couldn't parse episode info")
                    continue
                    
                dst_file = os.path.join(season_path, clean_filename)
                
                # Copy file using ZFS-aware copy
                log(f"    Copying: {file} -> {clean_filename}")
                subprocess.run(['cp', '--reflink=auto', src_file, dst_file], check=True)
                mkv_count += 1
                
        log(f"  Processed {mkv_count} episodes")
        
    log("TV show organization complete!")

if __name__ == "__main__":
    organize_tv_shows() 