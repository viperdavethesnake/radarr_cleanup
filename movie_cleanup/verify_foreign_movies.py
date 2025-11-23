import os
import json
import subprocess
import xml.etree.ElementTree as ET

FOREIGN_DIR = '/storage/media/servarr/foreign'

def get_mkv_info(mkv_path):
    cmd = ['mkvmerge', '-J', mkv_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)

def get_nfo_info(nfo_path):
    if not os.path.exists(nfo_path):
        return None
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        info = {}
        info['title'] = root.findtext('title')
        info['originaltitle'] = root.findtext('originaltitle')
        # Handle uniqueid properly
        for uid in root.findall('uniqueid'):
            if uid.get('type') == 'imdb':
                info['imdb'] = uid.text
            if uid.get('type') == 'tmdb':
                info['tmdb'] = uid.text
        # Fallback if not found in uniqueid
        if 'imdb' not in info:
            info['imdb'] = root.findtext('id')
            
        return info
    except Exception as e:
        print(f"Error parsing NFO {nfo_path}: {e}")
        return None

def verify_tags_content(mkv_path, nfo_data):
    cmd = ['mkvextract', mkv_path, 'tags', '-']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ❌ Failed to extract tags")
        return

    if not result.stdout.strip():
        print("  ⚠️ No tags content extracted")
        return

    print("  Metadata Tags:")
    checks = ['TITLE', 'DIRECTOR', 'IMDB', 'TMDB', 'SUMMARY']
    all_present = True
    for check in checks:
        if f"<Name>{check}</Name>" not in result.stdout:
            print(f"    ❌ {check} tag MISSING")
            all_present = False
    
    if all_present:
        print("    ✅ All standard tags (TITLE, DIRECTOR, IMDB, TMDB, SUMMARY) present")

    if nfo_data and nfo_data.get('title'):
        # Loose check because XML escaping might differ
        if nfo_data['title'] in result.stdout:
             print(f"    ✅ Title tag matches NFO: {nfo_data['title']}")

def verify_movie(folder_path):
    movie_name = os.path.basename(folder_path)
    print(f"\n----------------------------------------------------------------")
    print(f"Checking: {movie_name}")
    
    # Find MKV
    mkv_files = [f for f in os.listdir(folder_path) if f.endswith('.mkv')]
    if not mkv_files:
        print("❌ No MKV file found")
        return
    mkv_path = os.path.join(folder_path, mkv_files[0])
    print(f"File: {mkv_files[0]}")

    # Find NFO
    nfo_path = os.path.join(folder_path, 'movie.nfo')
    nfo_data = get_nfo_info(nfo_path)
    
    if not nfo_data:
        print("❌ NFO file missing or invalid")
    else:
        print("✅ NFO file present")

    # Check MKV
    mkv_data = get_mkv_info(mkv_path)
    if not mkv_data:
        print("❌ Failed to read MKV info")
        return

    # Verify Tracks
    print("Tracks:")
    for track in mkv_data.get('tracks', []):
        t_id = track['id']
        t_type = track['type']
        t_codec = track['codec']
        t_lang = track['properties'].get('language', 'und')
        t_default = track['properties'].get('default_track', False)
        t_forced = track['properties'].get('forced_track', False)
        t_name = track['properties'].get('track_name', '')
        
        default_str = " [Default]" if t_default else ""
        forced_str = " [Forced]" if t_forced else ""
        name_str = f" '{t_name}'" if t_name else ""
        
        icon = "  "
        if t_type == 'video': icon = "  📹"
        elif t_type == 'audio': icon = "  🔊"
        elif t_type == 'subtitles': icon = "  💬"
        
        print(f"{icon} {t_id}: {t_codec} ({t_lang}){default_str}{forced_str}{name_str}")

    # Verify Tags
    verify_tags_content(mkv_path, nfo_data)

def main():
    if not os.path.exists(FOREIGN_DIR):
        print(f"Directory not found: {FOREIGN_DIR}")
        return

    movies = sorted([os.path.join(FOREIGN_DIR, d) for d in os.listdir(FOREIGN_DIR) 
                     if os.path.isdir(os.path.join(FOREIGN_DIR, d))])
    
    for movie in movies:
        verify_movie(movie)

if __name__ == "__main__":
    main()
