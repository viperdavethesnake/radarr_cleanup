#!/usr/bin/env python3

import os, shutil, time, traceback, json, subprocess, re, signal
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from xml.etree.ElementTree import Element, SubElement, ElementTree
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========== CONFIG =============
SOURCE_DIR = './tvshows'
DEST_DIR = './tagged_tv'
FAILED_DIR = './failed_tv'
LOG_DIR = './logs'
MAX_WORKERS = 8
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    log("⚠️ Interrupt signal received, initiating graceful shutdown...")
    # Force exit after a short delay if needed
    import threading
    def force_exit():
        import time
        time.sleep(3)
        log("⚠️ Force exiting due to multiple interrupts...")
        os._exit(1)
    threading.Thread(target=force_exit, daemon=True).start()

# Set up signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    with open(os.path.join(LOG_DIR, 'tv_batch_cleaner_debug.log'), 'a') as f:
        f.write(line + '\n')

def timed(msg, func, *args, **kwargs):
    log(f"START: {msg}")
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
    except Exception as e:
        log(f"ERROR in {msg}: {e}\n{traceback.format_exc()}")
        raise
    elapsed = time.perf_counter() - start
    log(f"DONE: {msg} ({elapsed:.2f}s)")
    return result

def fast_copy(src, dst):
    subprocess.run(['cp', '--reflink=auto', src, dst], check=True, timeout=300)  # 5 minute timeout

def find_imdbid(folder, mkv=None):
    # Try .nfo file first — search the whole file for imdbid
    for f in os.listdir(folder):
        if f.endswith('.nfo'):
            with open(os.path.join(folder, f), 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
                match = re.search(r'tt\d{6,8}', content)
                if match:
                    return match.group(0)
    # Folder name
    match = re.search(r'tt\d{6,8}', os.path.basename(folder))
    if match:
        return match.group(0)
    # MKV file name
    if mkv:
        match = re.search(r'tt\d{6,8}', mkv)
        if match:
            return match.group(0)
    return None

def fetch_tmdb_metadata(imdbid):
    url = f'https://api.themoviedb.org/3/find/{imdbid}?api_key={TMDB_API_KEY}&external_source=imdb_id'
    resp = requests.get(url, timeout=30)  # Add timeout
    resp.raise_for_status()
    data = resp.json()
    d = None
    for key in ['tv_results', 'movie_results']:  # Prioritize TV results
        if data.get(key): d = data[key][0]; break
    if not d:
        raise Exception("TMDB lookup failed for " + str(imdbid))
    tmdb_id = d['id']
    url = f'https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits'
    resp = requests.get(url, timeout=30)  # Add timeout
    resp.raise_for_status()
    meta = resp.json()
    poster_url = 'https://image.tmdb.org/t/p/original' + meta['poster_path'] if meta.get('poster_path') else ''
    return meta, poster_url

def download_poster(url, dest):
    if not url: return
    resp = requests.get(url, stream=True, timeout=30)  # Add timeout
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

def strip_tags_attachments(mkvfile):
    # First, strip all tags
    cmd = ['mkvpropedit', mkvfile, '--tags', 'all:']
    subprocess.run(cmd, check=True, timeout=60)  # 1 minute timeout
    
    # Then, identify and delete attachments one by one
    out = subprocess.run(['mkvmerge', '--identify', mkvfile], capture_output=True, text=True, timeout=30)
    attachment_ids = []
    for line in out.stdout.splitlines():
        if "Attachment ID" in line:
            aid = line.split('Attachment ID')[1].split(':')[0].strip()
            attachment_ids.append(aid)
    
    # Delete attachments in reverse order to avoid ID shifting issues
    for aid in reversed(attachment_ids):
        try:
            cmd = ['mkvpropedit', mkvfile, '--delete-attachment', aid]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                # Check if it's just a "no attachment matched" warning
                if "No attachment matched" in result.stderr or "Warning: No attachment matched" in result.stderr:
                    log(f"  [INFO] Attachment {aid} already removed or doesn't exist, continuing...")
                else:
                    # It's a real error, raise it
                    result.check_returncode()
        except subprocess.TimeoutExpired:
            log(f"  [WARN] Timeout deleting attachment {aid}, continuing...")
        except Exception as e:
            # For any other exception, just log and continue
            log(f"  [WARN] Error deleting attachment {aid}: {e}, continuing...")

def write_json(meta, dest):
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

def write_tags_xml(meta, imdbid, dest):
    root = Element("Tags")
    tag = SubElement(root, "Tag")
    targets = SubElement(tag, "Targets")
    SubElement(targets, "TargetTypeValue").text = "50"
    
    # TV show specific tags
    SubElement(tag, "Simple").text = meta.get('name', '')
    SubElement(tag, "Simple").text = str(meta.get('id', ''))
    SubElement(tag, "Simple").text = meta.get('overview', '')
    SubElement(tag, "Simple").text = str(meta.get('number_of_seasons', ''))
    SubElement(tag, "Simple").text = str(meta.get('number_of_episodes', ''))
    SubElement(tag, "Simple").text = meta.get('first_air_date', '')
    SubElement(tag, "Simple").text = meta.get('last_air_date', '')
    
    # Genres
    for genre in meta.get('genres', []):
        SubElement(tag, "Simple").text = genre.get('name', '')
    
    # Networks
    for network in meta.get('networks', []):
        SubElement(tag, "Simple").text = network.get('name', '')
    
    tree = ElementTree(root)
    tree.write(dest, encoding='utf-8', xml_declaration=True)

def set_tags_in_mkv(mkvfile, tags_xml):
    subprocess.run(['mkvpropedit', mkvfile, '--tags', f'global:{tags_xml}'], check=True, timeout=60)

def write_nfo(meta, imdbid, dest):
    def safe_sub(parent, tag, val):
        if val:
            sub = SubElement(parent, tag)
            if isinstance(val, str):
                sub.text = val
            else:
                sub.text = str(val)
    
    root = Element("tvshow")
    safe_sub(root, "title", meta.get('name'))
    safe_sub(root, "originaltitle", meta.get('original_name'))
    safe_sub(root, "showtitle", meta.get('name'))
    safe_sub(root, "imdbid", imdbid)
    safe_sub(root, "tmdbid", str(meta.get('id')))
    safe_sub(root, "plot", meta.get('overview'))
    safe_sub(root, "outline", meta.get('overview'))
    safe_sub(root, "premiered", meta.get('first_air_date'))
    safe_sub(root, "status", meta.get('status'))
    safe_sub(root, "runtime", str(meta.get('episode_run_time', [0])[0]) if meta.get('episode_run_time') else None)
    safe_sub(root, "season", "1")  # Default season
    safe_sub(root, "episode", "1")  # Default episode
    
    # Genres
    for genre in meta.get('genres', []):
        safe_sub(root, "genre", genre.get('name'))
    
    # Networks
    for network in meta.get('networks', []):
        safe_sub(root, "studio", network.get('name'))
    
    tree = ElementTree(root)
    tree.write(dest, encoding='utf-8', xml_declaration=True)

def clean_show_name(meta):
    """Clean TV show name for folder naming"""
    name = meta.get('name', 'Unknown Show')
    # Remove special characters and replace spaces with underscores
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.replace(' ', '_').replace('.', '').strip()
    return name.strip('_')

def clean_episode_name(meta, episode_info, ext):
    """Clean episode name for file naming"""
    show_name = clean_show_name(meta)
    season_num = episode_info.get('season_number', 1)
    episode_num = episode_info.get('episode_number', 1)
    episode_title = episode_info.get('name', 'Episode')
    
    # Clean episode title - remove special chars and replace spaces with underscores
    episode_title = re.sub(r'[\\/:*?"<>|]', '', episode_title)
    episode_title = episode_title.replace(' ', '_').replace('.', '').strip()
    
    return f"{show_name}_S{season_num:02d}E{episode_num:02d}_{episode_title}{ext}"

def clean_show_folder(src_folder):
    global shutdown_requested
    if shutdown_requested:
        return
    
    base = os.path.basename(src_folder)
    log(f"\n▶ Processing TV Show: {base}")
    try:
        t0 = time.perf_counter()
        
        # Find all MKV files in the show folder (including seasons)
        mkv_files = []
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.lower().endswith('.mkv'):
                    mkv_files.append(os.path.join(root, file))
        
        if not mkv_files:
            log(f"❌ [SKIP] No MKV files found in {base}")
            return
        
        # Use the first MKV file to find IMDb ID
        first_mkv = mkv_files[0]
        imdbid = find_imdbid(src_folder, os.path.basename(first_mkv))
        log(f"  [IMDB] Found IMDb ID: {imdbid}")

        if not imdbid:
            log(f"❌ [SKIP] No IMDb ID found in {base}. Moving to failed.")
            failed = os.path.join(FAILED_DIR, base)
            try:
                shutil.move(src_folder, failed)
                log(f"  [FAILED] Moved to failed directory: {failed}")
            except Exception as e2:
                log(f"❌ Could not move to failed: {e2}")
            return

        # Get TMDb metadata, poster
        meta, poster_url = timed(f"TMDb lookup for {imdbid}", fetch_tmdb_metadata, imdbid)

        # New show folder name
        new_show_name = clean_show_name(meta)
        dst_show_folder = os.path.join(DEST_DIR, new_show_name)
        os.makedirs(dst_show_folder, exist_ok=True)

        # Process each MKV file
        for mkv_file in mkv_files:
            # Extract episode info from filename or path
            episode_info = extract_episode_info(mkv_file, meta)
            if not episode_info:
                log(f"  [WARN] Could not extract episode info from {mkv_file}")
                continue
            
            # Create season folder
            season_num = episode_info.get('season_number', 1)
            season_folder = os.path.join(dst_show_folder, f"Season {season_num:02d}")
            os.makedirs(season_folder, exist_ok=True)
            
            # New episode filename
            new_episode_name = clean_episode_name(meta, episode_info, os.path.splitext(mkv_file)[1])
            dst_episode = os.path.join(season_folder, new_episode_name)
            
            # Copy and process episode
            timed(f"Copy episode: {os.path.basename(mkv_file)} → {new_episode_name}", fast_copy, mkv_file, dst_episode)
            timed(f"Strip tags/attachments: {new_episode_name}", strip_tags_attachments, dst_episode)

        # Write show-level metadata files
        poster_path = os.path.join(dst_show_folder, "poster.jpg")
        timed(f"Download poster: {poster_url}", download_poster, poster_url, poster_path)
        timed(f"Write metadata.json", write_json, meta, os.path.join(dst_show_folder, "metadata.json"))
        tags_path = os.path.join(dst_show_folder, "tags.xml")
        timed(f"Write tags.xml", write_tags_xml, meta, imdbid, tags_path)
        timed(f"Write show.nfo", write_nfo, meta, imdbid, os.path.join(dst_show_folder, "show.nfo"))

        # Done - delete original folder
        timed(f"Delete original folder: {src_folder}", shutil.rmtree, src_folder)
        log(f"✔ [DONE] {base} total {(time.perf_counter()-t0):.2f}s\n")
        log(f"🔍 [DEBUG] Worker thread for {base} is about to return")

    except Exception as e:
        log(f"❌ ERROR processing {base}: {e}\n{traceback.format_exc()}")
        failed = os.path.join(FAILED_DIR, base)
        try:
            shutil.move(src_folder, failed)
            log(f"  [FAILED] Moved to failed directory: {failed}")
        except Exception as e2:
            log(f"❌ Could not move to failed: {e2}")
        log(f"🔍 [DEBUG] Worker thread for {base} is about to return after error")

def extract_episode_info(mkv_file, show_meta):
    """Extract season and episode information from filename or path"""
    filename = os.path.basename(mkv_file)
    path = os.path.dirname(mkv_file)
    
    # Common patterns: S01E02, 1x02, Season 1 Episode 2, etc.
    patterns = [
        r'S(\d{1,2})E(\d{1,2})',  # S01E02
        r'(\d{1,2})x(\d{1,2})',   # 1x02
        r'Season[._\s]*(\d{1,2})[._\s]*Episode[._\s]*(\d{1,2})',  # Season 1 Episode 2
        r'(\d{1,2})[._\s]*(\d{1,2})',  # 1.02 or 1_02
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            season_num = int(match.group(1))
            episode_num = int(match.group(2))
            
            # Try to extract episode title
            episode_title = "Episode"
            title_match = re.search(r'[S\d{1,2}E\d{1,2}][._\s]+(.+?)(?:\.mkv|$)', filename, re.IGNORECASE)
            if title_match:
                episode_title = title_match.group(1).strip('._- ')
            
            return {
                'season_number': season_num,
                'episode_number': episode_num,
                'name': episode_title
            }
    
    # Fallback: try to extract from path structure
    path_parts = path.split(os.sep)
    for part in path_parts:
        if 'season' in part.lower():
            season_match = re.search(r'(\d{1,2})', part)
            if season_match:
                return {
                    'season_number': int(season_match.group(1)),
                    'episode_number': 1,
                    'name': 'Episode'
                }
    
    return None

def main():
    global shutdown_requested
    
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)
    
    # Filter out non-TV show directories
    skip_dirs = {'failed', 'logs', 'scripts', 'saved', 'foreign', 'audiobooks', 'books', 'music', 'movies'}
    srcs = [os.path.join(SOURCE_DIR, d) for d in os.listdir(SOURCE_DIR) 
            if os.path.isdir(os.path.join(SOURCE_DIR, d)) and d not in skip_dirs]
    
    log(f"▶ Queued {len(srcs)} TV shows for cleaning with up to {MAX_WORKERS} workers")
    
    if srcs:
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                # Use as_completed instead of map for better interrupt handling
                futures = [pool.submit(clean_show_folder, src) for src in srcs]
                completed_count = 0
                
                try:
                    for future in as_completed(futures):
                        completed_count += 1
                        log(f"📊 Progress: {completed_count}/{len(futures)} TV shows completed")
                        
                        if shutdown_requested:
                            log("⚠️ Shutdown requested, cancelling remaining tasks...")
                            for f in futures:
                                f.cancel()
                            pool.shutdown(wait=False)
                            log("⚠️ Shutdown complete. Some TV shows may not have been processed.")
                            return
                        
                        try:
                            future.result(timeout=300)  # 5 minute timeout per future
                        except Exception as e:
                            log(f"❌ Worker thread error: {e}")
                            log(f"❌ Worker thread traceback: {traceback.format_exc()}")
                            
                except KeyboardInterrupt:
                    log("⚠️ Received interrupt signal, shutting down gracefully...")
                    shutdown_requested = True
                    # Cancel all pending futures
                    for f in futures:
                        f.cancel()
                    pool.shutdown(wait=False)
                    log("⚠️ Shutdown complete. Some TV shows may not have been processed.")
                    return
                    
        except KeyboardInterrupt:
            log("⚠️ Received interrupt signal during startup, exiting...")
            return
    
    log("All TV shows processed.")

if __name__ == "__main__":
    main() 