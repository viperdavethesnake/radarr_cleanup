#!/usr/bin/env python3

import os
import subprocess
import re

def add_simple_episode_metadata(mkv_file, episode_title):
    """Add simple episode metadata to MKV file"""
    try:
        # Add title to the MKV file
        cmd = ['mkvpropedit', '--set', f'title={episode_title}', mkv_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Added title '{episode_title}' to: {os.path.basename(mkv_file)}")
            return True
        else:
            print(f"❌ Error adding title to {mkv_file}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception adding title to {mkv_file}: {e}")
        return False

def process_all_episodes():
    """Process all episodes in the tagged directory"""
    base_dir = "/storage/media/servarr/tvshows_tagged/Glee_(2009)"
    
    if not os.path.exists(base_dir):
        print(f"❌ Directory not found: {base_dir}")
        return
    
    success_count = 0
    total_count = 0
    
    for season_folder in sorted(os.listdir(base_dir)):
        season_path = os.path.join(base_dir, season_folder)
        if not os.path.isdir(season_path) or not season_folder.startswith('Season_'):
            continue
        
        season_num = int(season_folder.split('_')[1])
        print(f"\nProcessing {season_folder}...")
        
        for filename in sorted(os.listdir(season_path)):
            if not filename.endswith('.mkv'):
                continue
            
            total_count += 1
            mkv_file = os.path.join(season_path, filename)
            
            # Extract episode title from filename: Glee_-_S01E01_-_Pilot.mkv
            match = re.match(r'Glee_-_S\d{2}E\d{2}_-_(.+?)\.mkv', filename)
            if match:
                episode_title = match.group(1).replace('_', ' ')
                success = add_simple_episode_metadata(mkv_file, episode_title)
                if success:
                    success_count += 1
            else:
                print(f"❌ Could not parse filename: {filename}")
    
    print(f"\n✅ Processing complete: {success_count}/{total_count} episodes updated")

if __name__ == "__main__":
    process_all_episodes() 