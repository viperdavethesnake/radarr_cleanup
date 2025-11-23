#!/usr/bin/env python3

import os, shutil, subprocess, json, time, traceback, re
from concurrent.futures import ThreadPoolExecutor

TAGGED_DIR = './tagged_tv'
CLEANED_DIR = './cleaned_tv'
FAILED_DIR = './failed_tv'
LOG_DIR = './logs'
MAX_WORKERS = 4

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    with open(os.path.join(LOG_DIR, 'tv_remux_cleanroom_debug.log'), 'a') as f:
        f.write(line + '\n')

def find_main_mkv(folder):
    for f in os.listdir(folder):
        if f.lower().endswith('.mkv'):
            return f
    return None

def is_eng_lang(lang):
    if not lang or lang.lower() in ('', 'und', 'en', 'eng', 'en-us', 'en-gb'):
        return True
    return False

def is_sub_junk(track):
    # Commentary, SDH, HI, forced subs
    name = track.get('properties', {}).get('track_name', '') or ''
    name_low = name.lower()
    if (
        'commentary' in name_low
        or 'sdh' in name_low
        or 'hearing' in name_low
        or 'impaired' in name_low
        or 'hi ' in name_low
        or 'hi-' in name_low
        or 'hi/' in name_low
        or 'forced' in name_low
        or track.get('properties', {}).get('flag_commentary')
        or track.get('properties', {}).get('flag_hearing_impaired')
        or track.get('properties', {}).get('forced_track')
    ):
        return True
    return False

def pick_best_audio(tracks):
    # Prefer English, pick best codec order
    codec_rank = [
        'A_TRUEHD', 'A_DTS', 'A_DTSHD', 'A_EAC3', 'A_AC3', 'A_AAC', 'A_MP3'
    ]
    audios = []
    for t in tracks:
        if t['type'] == 'audio' and is_eng_lang(t['properties'].get('language')):
            audios.append(t)
    if not audios:
        # Try any audio, fallback
        audios = [t for t in tracks if t['type'] == 'audio']
    if not audios:
        return None
    # Rank by codec preference
    def codec_score(track):
        codec_id = (track['properties'].get('codec_id') or '').upper()
        for i, cid in enumerate(codec_rank):
            if cid in codec_id:
                return i
        return len(codec_rank)
    audios.sort(key=codec_score)
    return audios[0]

def get_video_stream_info(mkv_path):
    """Extract video stream information using ffprobe"""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
           '-show_streams', '-select_streams', 'v:0', mkv_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data['streams'][0] if data['streams'] else {}
    except Exception as e:
        log(f"  [WARN] Could not get video info: {e}")
        return {}

def get_audio_stream_info(mkv_path):
    """Extract audio stream information using ffprobe"""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
           '-show_streams', '-select_streams', 'a:0', mkv_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data['streams'][0] if data['streams'] else {}
    except Exception as e:
        log(f"  [WARN] Could not get audio info: {e}")
        return {}

def enhanced_episode_name(meta, episode_info, video_info, audio_info, ext):
    """Create enhanced episode filename with technical details"""
    show_name = meta.get('name', 'Unknown Show')
    season_num = episode_info.get('season_number', 1)
    episode_num = episode_info.get('episode_number', 1)
    episode_title = episode_info.get('name', 'Episode')
    
    # Clean show name and episode title
    show_name = re.sub(r'[\\/:*?"<>|]', '', show_name)
    show_name = show_name.replace(' ', '_').replace('.', '').strip()
    
    episode_title = re.sub(r'[\\/:*?"<>|]', '', episode_title)
    episode_title = episode_title.replace(' ', '_').replace('.', '').strip()
    
    # Get technical details
    resolution = video_info.get('height', 'Unknown')
    video_codec = video_info.get('codec_name', 'Unknown')
    audio_codec = audio_info.get('codec_name', 'Unknown')
    
    # Clean codec names
    video_codec = video_codec.replace('-', '').replace('.', '')
    audio_codec = audio_codec.replace('-', '').replace('.', '')
    
    return f"{show_name}_S{season_num:02d}E{episode_num:02d}_{episode_title}_[{resolution}p_{video_codec}_{audio_codec}]{ext}"

def pick_best_subtitle(tracks):
    # Only accept SRT and ASS subtitle formats, prioritize SRT
    allowed_formats = ['S_TEXT/UTF8', 'S_TEXT/ASS', 'S_TEXT/SSA']
    
    # Find English subtitles with allowed formats
    valid_subs = []
    for t in tracks:
        if (t['type'] == 'subtitles' and 
            is_eng_lang(t['properties'].get('language')) and
            t['properties'].get('codec_id') in allowed_formats):
            valid_subs.append(t)
    
    if not valid_subs:
        return None
    
    # Prioritize SRT over ASS
    srt_subs = [t for t in valid_subs if t['properties'].get('codec_id') == 'S_TEXT/UTF8']
    if srt_subs:
        return srt_subs[0]  # Return first SRT subtitle
    
    # Fallback to ASS if no SRT available
    ass_subs = [t for t in valid_subs if t['properties'].get('codec_id') in ['S_TEXT/ASS', 'S_TEXT/SSA']]
    if ass_subs:
        return ass_subs[0]  # Return first ASS subtitle
    
    return None

def parse_mkv_tracks(mkv_path):
    result = subprocess.run(['mkvmerge', '-J', mkv_path], capture_output=True, text=True)
    info = json.loads(result.stdout)
    return info.get('tracks', [])

def remux_episode(tagged_folder, episode_file):
    """Remux a single episode file"""
    base = os.path.basename(tagged_folder)
    episode_name = os.path.basename(episode_file)
    log(f"  ▶ Remuxing episode: {episode_name}")
    
    try:
        t0 = time.perf_counter()
        src_mkv = episode_file
        
        # Get technical info for enhanced naming
        video_info = get_video_stream_info(src_mkv)
        audio_info = get_audio_stream_info(src_mkv)
        
        # Try to get metadata for enhanced naming
        meta = {}
        episode_info = {}
        try:
            # Try to read metadata.json if it exists
            metadata_file = os.path.join(tagged_folder, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    meta = json.load(f)
            
            # Try to extract episode info from filename
            episode_match = re.search(r'S(\d{2})E(\d{2})', episode_name)
            if episode_match:
                season_num = int(episode_match.group(1))
                episode_num = int(episode_match.group(2))
                episode_info = {
                    'season_number': season_num,
                    'episode_number': episode_num,
                    'name': 'Episode'  # Default name
                }
        except Exception as e:
            log(f"  [WARN] Could not read metadata: {e}")
        
        # Create destination folder structure
        relative_path = os.path.relpath(episode_file, tagged_folder)
        dst_folder = os.path.join(CLEANED_DIR, base, os.path.dirname(relative_path))
        os.makedirs(dst_folder, exist_ok=True)
        
        # Create enhanced filename if we have metadata, otherwise use original
        if meta and episode_info and video_info and audio_info:
            enhanced_name = enhanced_episode_name(meta, episode_info, video_info, audio_info, '.mkv')
            dst_mkv = os.path.join(dst_folder, enhanced_name)
            log(f"  [NAME] Using enhanced filename: {enhanced_name}")
        else:
            dst_mkv = os.path.join(dst_folder, os.path.basename(episode_file))
            log(f"  [NAME] Using original filename: {episode_name}")

        tracks = parse_mkv_tracks(src_mkv)
        if not tracks:
            raise Exception("No tracks found in MKV")

        # --- Select tracks ---
        video_track_ids = [str(t['id']) for t in tracks if t['type'] == 'video']
        video_id = video_track_ids[0] if video_track_ids else None

        audio = pick_best_audio(tracks)
        audio_id = str(audio['id']) if audio else None

        subtitle = pick_best_subtitle(tracks)
        subtitle_id = str(subtitle['id']) if subtitle else None

        # --- Build mkvmerge cmd ---
        cmd = ['mkvmerge', '-o', dst_mkv, '--no-chapters', '--no-attachments']

        # Video
        if video_id is not None:
            cmd += ['--video-tracks', video_id, '--language', f'{video_id}:eng']
        # Audio
        if audio_id is not None:
            cmd += ['--audio-tracks', audio_id, '--language', f'{audio_id}:eng']
        # Subtitle
        if subtitle_id is not None:
            cmd += ['--subtitle-tracks', subtitle_id, '--language', f'{subtitle_id}:eng', '--default-track-flag', f'{subtitle_id}:0']
        else:
            cmd += ['--no-subtitles']

        cmd += [src_mkv]

        log(f"    [CMD] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

        log(f"    ✔ [DONE] Remuxed {episode_name} in {time.perf_counter()-t0:.2f}s")
        return True

    except Exception as e:
        log(f"    ❌ ERROR remuxing {episode_name}: {e}")
        return False

def remux_show_folder(tagged_folder):
    """Remux all episodes in a TV show folder"""
    base = os.path.basename(tagged_folder)
    log(f"\n▶ Remuxing TV Show: {base}")
    try:
        t0 = time.perf_counter()
        
        # Find all MKV files in the show folder (including seasons)
        mkv_files = []
        for root, dirs, files in os.walk(tagged_folder):
            for file in files:
                if file.lower().endswith('.mkv'):
                    mkv_files.append(os.path.join(root, file))
        
        if not mkv_files:
            raise Exception(f"No MKV files found in {tagged_folder}")

        # Create destination show folder
        dst_show_folder = os.path.join(CLEANED_DIR, base)
        os.makedirs(dst_show_folder, exist_ok=True)

        # Process each episode
        successful_episodes = 0
        total_episodes = len(mkv_files)
        
        for mkv_file in mkv_files:
            if remux_episode(tagged_folder, mkv_file):
                successful_episodes += 1

        # Copy show-level metadata files
        for fname in ['show.nfo', 'poster.jpg', 'metadata.json', 'tags.xml']:
            src_file = os.path.join(tagged_folder, fname)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(dst_show_folder, fname))

        log(f"✔ [DONE] Remuxed {base}: {successful_episodes}/{total_episodes} episodes in {time.perf_counter()-t0:.2f}s")
        
        # Delete original folder after successful remux
        if successful_episodes == total_episodes:
            try:
                log(f"  [CLEANUP] Deleting original folder: {tagged_folder}")
                shutil.rmtree(tagged_folder)
                log(f"  [CLEANUP] ✔ Original folder deleted successfully")
            except Exception as cleanup_error:
                log(f"❌ [CLEANUP] Failed to delete original folder: {cleanup_error}")
                log(f"  [CLEANUP] Remux successful but manual cleanup needed for: {tagged_folder}")
        else:
            log(f"  [CLEANUP] Skipping deletion - only {successful_episodes}/{total_episodes} episodes succeeded")
            
    except Exception as e:
        log(f"❌ ERROR: {e}\n{traceback.format_exc()}")
        
        # Clean up failed output
        try:
            dst_show_folder = os.path.join(CLEANED_DIR, base)
            if os.path.isdir(dst_show_folder):
                shutil.rmtree(dst_show_folder, ignore_errors=True)
        except Exception as e2:
            log(f"❌ Secondary cleanup failed: {e2}")
        
        # Move failed folder to ./failed directory
        failed_folder = os.path.join(FAILED_DIR, base)
        try:
            os.makedirs(FAILED_DIR, exist_ok=True)
            if os.path.exists(failed_folder):
                shutil.rmtree(failed_folder, ignore_errors=True)
            shutil.move(tagged_folder, failed_folder)
            log(f"  [FAILED] Moved to failed directory: {failed_folder}")
        except Exception as e3:
            log(f"❌ Could not move to failed directory: {e3}")

def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CLEANED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)
    
    # Filter out non-TV show directories
    skip_dirs = {'failed', 'logs', 'scripts', 'saved', 'foreign', 'audiobooks', 'books', 'music', 'movies'}
    folders = [os.path.join(TAGGED_DIR, d) for d in os.listdir(TAGGED_DIR)
               if os.path.isdir(os.path.join(TAGGED_DIR, d)) and d not in skip_dirs]
    
    log(f"▶ Starting TV show cleanroom remux for {len(folders)} shows (max {MAX_WORKERS} threads)")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(remux_show_folder, folders))
    log("✅ All TV show remux operations completed.")

if __name__ == "__main__":
    main() 