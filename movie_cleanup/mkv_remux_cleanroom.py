#!/usr/bin/env python3

import os, shutil, subprocess, json, time, traceback, re
from concurrent.futures import ThreadPoolExecutor, as_completed

TAGGED_DIR = './tagged'
CLEANED_DIR = './cleaned'
FAILED_DIR = './failed'
LOG_DIR = './logs'
MAX_WORKERS = 12

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    with open(os.path.join(LOG_DIR, 'remux_cleanroom_debug.log'), 'a') as f:
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

def enhanced_file_name(meta, imdbid, video_info, audio_info, ext):
    """Create enhanced filename with technical details"""
    title = meta.get('title', 'Unknown')
    year = meta.get('release_date', '')[:4]
    
    # Clean title - replace spaces with underscores
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)
    safe_title = safe_title.replace(' ', '_').replace('.', '').strip()
    
    # Get technical details
    resolution = video_info.get('height', 'Unknown')
    video_codec = video_info.get('codec_name', 'Unknown')
    audio_codec = audio_info.get('codec_name', 'Unknown')
    
    # Clean codec names
    video_codec = video_codec.replace('-', '').replace('.', '')
    audio_codec = audio_codec.replace('-', '').replace('.', '')
    
    if year:
        return f"{safe_title}_({year})_[{resolution}p_{video_codec}_{audio_codec}]{ext}"
    return f"{safe_title}_[{resolution}p_{video_codec}_{audio_codec}]{ext}"

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

def clean_nfo_title(nfo_path, dst_path):
    try:
        with open(nfo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find current title
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            current_title = title_match.group(1)
            # Clean it
            cleaned = current_title.replace('_', ' ')
            cleaned = re.sub(r'\s*\(\d{4}\)$', '', cleaned).strip()
            
            if cleaned != current_title:
                content = content.replace(f'<title>{current_title}</title>', f'<title>{cleaned}</title>')
                log(f"  [NFO] Fixed title: '{current_title}' -> '{cleaned}'")
        
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    except Exception as e:
        log(f"  [WARN] Failed to clean NFO {nfo_path}: {e}")
        # Fallback to copy
        shutil.copy2(nfo_path, dst_path)

def remux_folder(tagged_folder):
    base = os.path.basename(tagged_folder)
    log(f"\n▶ Remuxing: {base}")
    try:
        t0 = time.perf_counter()
        mkv_file = find_main_mkv(tagged_folder)
        if not mkv_file:
            raise Exception(f"No MKV file found in {tagged_folder}")
        src_mkv = os.path.join(tagged_folder, mkv_file)
        dst_folder = os.path.join(CLEANED_DIR, base)
        os.makedirs(dst_folder, exist_ok=True)
        
        # Get technical info for enhanced naming
        video_info = get_video_stream_info(src_mkv)
        audio_info = get_audio_stream_info(src_mkv)
        
        # Try to get metadata for enhanced naming
        meta = {}
        imdbid = None
        try:
            # Try to read metadata.json if it exists
            metadata_file = os.path.join(tagged_folder, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    meta = json.load(f)
                # Try to extract imdbid from folder name or metadata
                imdbid_match = re.search(r'tt\d{6,8}', base)
                if imdbid_match:
                    imdbid = imdbid_match.group(0)
        except Exception as e:
            log(f"  [WARN] Could not read metadata: {e}")
        
        # Create enhanced filename if we have metadata, otherwise use original
        if meta and video_info and audio_info:
            enhanced_name = enhanced_file_name(meta, imdbid, video_info, audio_info, '.mkv')
            dst_mkv = os.path.join(dst_folder, enhanced_name)
            log(f"  [NAME] Using enhanced filename: {enhanced_name}")
        else:
            dst_mkv = os.path.join(dst_folder, mkv_file)
            log(f"  [NAME] Using original filename: {mkv_file}")

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

        log(f"  [CMD] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

        # --- Copy movie.nfo and poster.jpg ---
        for fname in ['movie.nfo', 'poster.jpg']:
            src_file = os.path.join(tagged_folder, fname)
            if os.path.isfile(src_file):
                if fname == 'movie.nfo':
                    clean_nfo_title(src_file, os.path.join(dst_folder, fname))
                else:
                    shutil.copy2(src_file, os.path.join(dst_folder, fname))

        log(f"✔ [DONE] Remuxed {base} in {time.perf_counter()-t0:.2f}s")
        
        # Delete original folder after successful remux
        try:
            log(f"  [CLEANUP] Deleting original folder: {tagged_folder}")
            shutil.rmtree(tagged_folder)
            log(f"  [CLEANUP] ✔ Original folder deleted successfully")
        except Exception as cleanup_error:
            log(f"❌ [CLEANUP] Failed to delete original folder: {cleanup_error}")
            # Don't fail the entire operation for cleanup issues
            log(f"  [CLEANUP] Remux successful but manual cleanup needed for: {tagged_folder}")
    except Exception as e:
        log(f"❌ ERROR: {e}\n{traceback.format_exc()}")
        
        # Clean up failed output
        try:
            if os.path.isdir(dst_folder):
                shutil.rmtree(dst_folder, ignore_errors=True)
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
    folders = [os.path.join(TAGGED_DIR, d) for d in os.listdir(TAGGED_DIR)
               if os.path.isdir(os.path.join(TAGGED_DIR, d))]
    log(f"▶ Starting cleanroom remux for {len(folders)} folders (max {MAX_WORKERS} threads)")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(remux_folder, folders))
    log("✅ All remux operations completed.")

if __name__ == "__main__":
    main()

