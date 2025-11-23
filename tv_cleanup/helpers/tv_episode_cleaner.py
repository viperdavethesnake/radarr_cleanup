#!/usr/bin/env python3
"""
TV Episode Cleaner - Clean individual TV episodes while preserving Sonarr structure
Based on movie cleaning approach but adapted for TV shows
"""

import os
import subprocess
import json
import time
import re
import xml.etree.ElementTree as ET
from pathlib import Path

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")

def strip_mkv_tags_and_attachments(mkv_file):
    """Strip all tags and attachments from MKV file"""
    log(f"  [CLEAN] Stripping tags and attachments from {os.path.basename(mkv_file)}")
    
    try:
        # Strip all tags
        subprocess.run(['mkvpropedit', '--tags', 'all:', mkv_file], 
                      check=True, capture_output=True, timeout=60)
        
        # Get attachment list
        result = subprocess.run(['mkvmerge', '--identify', mkv_file], 
                               capture_output=True, text=True, timeout=30)
        
        # Remove attachments one by one
        attachment_ids = []
        for line in result.stdout.splitlines():
            if "Attachment ID" in line:
                aid = line.split('Attachment ID')[1].split(':')[0].strip()
                attachment_ids.append(aid)
        
        # Delete attachments in reverse order
        for aid in reversed(attachment_ids):
            try:
                subprocess.run(['mkvpropedit', '--delete-attachment', aid, mkv_file], 
                              check=True, capture_output=True, timeout=60)
            except subprocess.CalledProcessError:
                # Attachment might already be gone, continue
                pass
        
        log(f"  [CLEAN] ✅ Stripped tags and attachments")
        return True
        
    except Exception as e:
        log(f"  [CLEAN] ❌ Error: {e}")
        return False

def set_mkv_languages(mkv_file):
    """Set proper language tags for video and audio tracks"""
    log(f"  [LANG] Setting language tags")
    
    try:
        # Get track info
        result = subprocess.run(['mkvmerge', '-J', mkv_file], 
                               capture_output=True, text=True, timeout=30)
        tracks = json.loads(result.stdout).get('tracks', [])
        
        # Set video track to English (use track number, not ID)
        video_tracks = [t for t in tracks if t['type'] == 'video']
        for track in video_tracks:
            track_num = track.get('properties', {}).get('number', track['id'] + 1)
            subprocess.run(['mkvpropedit', '--edit', f'track:{track_num}', 
                           '--set', 'language=eng', mkv_file], 
                          check=True, capture_output=True, timeout=60)
        
        # Set audio tracks to English
        audio_tracks = [t for t in tracks if t['type'] == 'audio']
        for track in audio_tracks:
            track_num = track.get('properties', {}).get('number', track['id'] + 1)
            subprocess.run(['mkvpropedit', '--edit', f'track:{track_num}', 
                           '--set', 'language=eng', mkv_file], 
                          check=True, capture_output=True, timeout=60)
        
        # Set subtitle tracks to English
        subtitle_tracks = [t for t in tracks if t['type'] == 'subtitles']
        for track in subtitle_tracks:
            track_num = track.get('properties', {}).get('number', track['id'] + 1)
            subprocess.run(['mkvpropedit', '--edit', f'track:{track_num}', 
                           '--set', 'language=eng', mkv_file], 
                          check=True, capture_output=True, timeout=60)
        
        log(f"  [LANG] ✅ Set all tracks to English")
        return True
        
    except Exception as e:
        log(f"  [LANG] ❌ Error: {e}")
        return False

def create_episode_tags_xml(show_nfo, episode_nfo):
    """Create clean tags XML from NFO files"""
    log(f"  [TAGS] Creating episode tags XML")
    
    try:
        # Parse show NFO
        show_tree = ET.parse(show_nfo)
        show_root = show_tree.getroot()
        
        # Parse episode NFO
        episode_tree = ET.parse(episode_nfo)
        episode_root = episode_tree.getroot()
        
        # Create tags XML
        tags_root = ET.Element("Tags")
        tag = ET.SubElement(tags_root, "Tag")
        targets = ET.SubElement(tag, "Targets")
        ET.SubElement(targets, "TargetTypeValue").text = "50"
        
        # Show metadata
        show_title = show_root.find('title')
        if show_title is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "SHOW_TITLE"
            ET.SubElement(s, "String").text = show_title.text
        
        # Episode metadata
        episode_title = episode_root.find('title')
        if episode_title is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "EPISODE_TITLE"
            ET.SubElement(s, "String").text = episode_title.text
        
        season = episode_root.find('season')
        if season is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "SEASON"
            ET.SubElement(s, "String").text = season.text
        
        episode = episode_root.find('episode')
        if episode is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "EPISODE"
            ET.SubElement(s, "String").text = episode.text
        
        aired = episode_root.find('aired')
        if aired is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "AIR_DATE"
            ET.SubElement(s, "String").text = aired.text
        
        plot = episode_root.find('plot')
        if plot is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "PLOT"
            ET.SubElement(s, "String").text = plot.text
        
        # IDs
        for uniqueid in episode_root.findall('uniqueid'):
            id_type = uniqueid.get('type', '').upper()
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = f"EPISODE_{id_type}_ID"
            ET.SubElement(s, "String").text = uniqueid.text
        
        # Show IDs
        for uniqueid in show_root.findall('uniqueid'):
            id_type = uniqueid.get('type', '').upper()
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = f"SHOW_{id_type}_ID"
            ET.SubElement(s, "String").text = uniqueid.text
        
        # Genres
        for genre in show_root.findall('genre'):
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "GENRE"
            ET.SubElement(s, "String").text = genre.text
        
        # Studio/Network
        studio = show_root.find('studio')
        if studio is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "STUDIO"
            ET.SubElement(s, "String").text = studio.text
        
        # Rating
        rating = show_root.find('rating')
        if rating is not None:
            s = ET.SubElement(tag, "Simple")
            ET.SubElement(s, "Name").text = "RATING"
            ET.SubElement(s, "String").text = rating.text
        
        # Write tags XML
        tags_xml = os.path.join(os.path.dirname(episode_nfo), "episode_tags.xml")
        tree = ET.ElementTree(tags_root)
        tree.write(tags_xml, encoding="utf-8", xml_declaration=True)
        
        log(f"  [TAGS] ✅ Created episode tags XML")
        return tags_xml
        
    except Exception as e:
        log(f"  [TAGS] ❌ Error: {e}")
        return None

def inject_tags_into_mkv(mkv_file, tags_xml):
    """Inject tags XML into MKV file"""
    log(f"  [INJECT] Injecting tags into MKV")
    
    try:
        subprocess.run(['mkvpropedit', '--tags', f'all:{tags_xml}', mkv_file], 
                      check=True, capture_output=True, timeout=60)
        log(f"  [INJECT] ✅ Tags injected successfully")
        return True
        
    except Exception as e:
        log(f"  [INJECT] ❌ Error: {e}")
        return False

def clean_episode(episode_path):
    """Clean a single TV episode"""
    episode_name = os.path.basename(episode_path)
    log(f"\n🎬 Cleaning episode: {episode_name}")
    
    # Find NFO files
    episode_nfo = episode_path.replace('.mkv', '.nfo')
    show_nfo = os.path.join(os.path.dirname(os.path.dirname(episode_path)), 'tvshow.nfo')
    
    if not os.path.exists(episode_nfo):
        log(f"  ❌ Episode NFO not found: {episode_nfo}")
        return False
    
    if not os.path.exists(show_nfo):
        log(f"  ❌ Show NFO not found: {show_nfo}")
        return False
    
    log(f"  [INFO] Episode NFO: {os.path.basename(episode_nfo)}")
    log(f"  [INFO] Show NFO: {os.path.basename(show_nfo)}")
    
    # Step 1: Strip tags and attachments
    if not strip_mkv_tags_and_attachments(episode_path):
        return False
    
    # Step 2: Set proper languages
    if not set_mkv_languages(episode_path):
        return False
    
    # Step 3: Create clean tags XML
    tags_xml = create_episode_tags_xml(show_nfo, episode_nfo)
    if not tags_xml:
        return False
    
    # Step 4: Inject tags into MKV
    if not inject_tags_into_mkv(episode_path, tags_xml):
        return False
    
    # Step 5: Clean up temporary files
    try:
        os.remove(tags_xml)
        log(f"  [CLEANUP] ✅ Removed temporary tags XML")
    except:
        pass
    
    log(f"  ✅ Episode cleaned successfully!")
    return True

def main():
    """Main function - clean the Tulsa King episode"""
    episode_path = "/storage/media/servarr/tvshows/Tulsa King (2022) [tvdbid-413215]/Season 03/Tulsa King (2022) - S03E01 - Blood and Bourbon [WEBDL-2160p][EAC3 5.1][h265]-WtF.mkv"
    
    if not os.path.exists(episode_path):
        log(f"❌ Episode not found: {episode_path}")
        return 1
    
    log("🧹 Starting TV Episode Cleaning")
    log(f"📁 Episode: {os.path.basename(episode_path)}")
    
    success = clean_episode(episode_path)
    
    if success:
        log("\n✅ Episode cleaning completed successfully!")
        return 0
    else:
        log("\n❌ Episode cleaning failed!")
        return 1

if __name__ == "__main__":
    exit(main())
