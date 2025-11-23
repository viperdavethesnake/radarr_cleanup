#!/usr/bin/env python3

import os, shutil, time, traceback, json, subprocess, re, signal
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from xml.etree.ElementTree import Element, SubElement, ElementTree
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========== CONFIG =============
SOURCE_DIR = './movies'
DEST_DIR = './tagged'
FAILED_DIR = './failed'
LOG_DIR = './logs'
MAX_WORKERS = 8
TMDB_API_KEY = os.getenv('TMDB_API_KEY', 'your_api_key_here')

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
    with open(os.path.join(LOG_DIR, 'batch_cleaner_debug.log'), 'a') as f:
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
    for key in ['movie_results', 'tv_results']:
        if data.get(key): d = data[key][0]; break
    if not d:
        raise Exception("TMDB lookup failed for " + str(imdbid))
    tmdb_id = d['id']
    url = f'https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits,belongs_to_collection'
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
    
    # Basic metadata
    tags_data = [
        ("TITLE", meta.get("title") or meta.get("name")),
        ("YEAR", str(meta.get("release_date", "")[:4])),
        ("DIRECTOR", next((c['name'] for c in meta.get('credits', {}).get('crew', []) if c.get('job') == 'Director'), "")),
        ("GENRE", ", ".join([g['name'] for g in meta.get('genres', [])])),
        ("IMDB", imdbid),
        ("TMDB", str(meta.get("id"))),
        ("PLOT", meta.get("overview", "")),
    ]
    
    # Add collection data if available
    collection = meta.get('belongs_to_collection')
    if collection:
        tags_data.extend([
            ("COLLECTION", collection.get('name', '')),
            ("COLLECTION_ID", str(collection.get('id', ''))),
        ])
    
    for k, v in tags_data:
        if v:
            s = SubElement(tag, "Simple")
            SubElement(s, "Name").text = k
            SubElement(s, "String").text = v
    
    # ✅ Add box set to tags.xml
    if meta.get("belongs_to_collection"):
        s = SubElement(tag, "Simple")
        SubElement(s, "Name").text = "SET"
        SubElement(s, "String").text = meta["belongs_to_collection"].get("name")

        s2 = SubElement(tag, "Simple")
        SubElement(s2, "Name").text = "SETID"
        SubElement(s2, "String").text = str(meta["belongs_to_collection"].get("id"))
    ElementTree(root).write(dest, encoding="utf-8", xml_declaration=True)

def set_tags_in_mkv(mkvfile, tags_xml):
    subprocess.run(['mkvpropedit', mkvfile, '--tags', f'all:{tags_xml}'], check=True, timeout=60)  # 1 minute timeout

def write_nfo(meta, imdbid, dest):
    root = Element('movie')

    def safe_sub(parent, tag, val):
        if val: SubElement(parent, tag).text = val

    # Ensure title is clean (no underscores, no year suffix)
    title = meta.get('title')
    if title:
        title = title.replace('_', ' ')
        title = re.sub(r'\s*\(\d{4}\)$', '', title)
    
    safe_sub(root, 'title', title)
    safe_sub(root, 'originaltitle', meta.get('original_title'))
    safe_sub(root, 'year', meta.get('release_date', '')[:4])
    safe_sub(root, 'releasedate', meta.get('release_date'))
    safe_sub(root, 'plot', meta.get('overview'))
    safe_sub(root, 'tagline', meta.get('tagline'))
    safe_sub(root, 'tmdbid', str(meta.get('id')))
    safe_sub(root, 'imdbid', imdbid)
    safe_sub(root, 'genre', ', '.join([g['name'] for g in meta.get('genres', [])]))
    safe_sub(root, 'rating', str(meta.get('vote_average', '')))
    safe_sub(root, 'votes', str(meta.get('vote_count', '')))
    safe_sub(root, 'runtime', str(meta.get('runtime', '')))

    for studio in meta.get('production_companies', []):
        safe_sub(root, 'studio', studio.get('name'))

    directors = [c['name'] for c in meta.get('credits', {}).get('crew', []) if c.get('job') == 'Director']
    for director in directors:
        safe_sub(root, 'director', director)

    for a in meta.get('credits', {}).get('cast', [])[:8]:
        actor_el = SubElement(root, 'actor')
        safe_sub(actor_el, 'name', a.get('name'))
        safe_sub(actor_el, 'role', a.get('character'))

    for country in meta.get('production_countries', []):
        safe_sub(root, 'country', country.get('name'))

    # ✅ Add box set info
    collection = meta.get('belongs_to_collection')
    if collection:
        safe_sub(root, 'set', collection.get("name"))
        safe_sub(root, 'setid', str(collection.get("id")))
        safe_sub(root, 'setoverview', collection.get("overview"))

    ElementTree(root).write(dest, encoding="utf-8", xml_declaration=True)

def clean_folder_name(meta):
    title = meta.get('title') or meta.get('name') or "Unknown"
    year = meta.get('release_date', '')[:4]
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)
    safe_title = safe_title.replace(' ', '_').replace('.', '').strip()
    if year:
        return f"{safe_title}_({year})"
    return safe_title

def clean_file_name(meta, ext):
    title = meta.get('title') or meta.get('name') or "Unknown"
    year = meta.get('release_date', '')[:4]
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)
    safe_title = safe_title.replace(' ', '_').replace('.', '').strip()
    if year:
        return f"{safe_title}_({year}){ext}"
    return f"{safe_title}{ext}"

def clean_folder(src_folder):
    global shutdown_requested
    if shutdown_requested:
        return
    
    base = os.path.basename(src_folder)
    log(f"\n▶ Processing: {base}")
    try:
        t0 = time.perf_counter()
        # Find MKV
        mkv = next(f for f in os.listdir(src_folder) if f.lower().endswith('.mkv'))
        src_mkv = os.path.join(src_folder, mkv)

        # Try to find imdbid
        imdbid = find_imdbid(src_folder, mkv)
        log(f"  [IMDB] Found IMDb ID: {imdbid}")

        if not imdbid:
            log(f"❌ [SKIP] No IMDb ID found in {base}. Moving to failed.")
            failed = os.path.join(FAILED_DIR, base)
            try:
                shutil.move(src_folder, failed)
                log(f"  [FAILED] Moved to failed directory: {failed}")
            except Exception as e2:
                log(f"❌ Could not move to failed: {e2}")
            return  # Skip further processing!

        # Get TMDb metadata, poster
        meta, poster_url = timed(f"TMDb lookup for {imdbid}", fetch_tmdb_metadata, imdbid)

        # New folder/file names
        new_base = clean_folder_name(meta)
        dst_folder = os.path.join(DEST_DIR, new_base)
        os.makedirs(dst_folder, exist_ok=True)
        new_mkv_name = clean_file_name(meta, os.path.splitext(mkv)[1])
        dst_mkv = os.path.join(dst_folder, new_mkv_name)

        # Copy MKV to destination (canonical name)
        timed(f"Copy MKV: {src_mkv} → {dst_mkv}", fast_copy, src_mkv, dst_mkv)

        # Strip tags and attachments
        timed(f"Strip tags/attachments: {dst_mkv}", strip_tags_attachments, dst_mkv)

        # Write metadata files
        poster_path = os.path.join(dst_folder, "poster.jpg")
        timed(f"Download poster: {poster_url}", download_poster, poster_url, poster_path)
        timed(f"Write metadata.json", write_json, meta, os.path.join(dst_folder, "metadata.json"))
        tags_path = os.path.join(dst_folder, "tags.xml")
        timed(f"Write tags.xml", write_tags_xml, meta, imdbid, tags_path)
        timed(f"Inject tags.xml into MKV", set_tags_in_mkv, dst_mkv, tags_path)
        timed(f"Write movie.nfo", write_nfo, meta, imdbid, os.path.join(dst_folder, "movie.nfo"))

        # Remove any scene NFOs in the new folder
        for f in os.listdir(dst_folder):
            if f.lower().endswith('.nfo') and f != 'movie.nfo':
                try:
                    os.remove(os.path.join(dst_folder, f))
                    log(f"  [NFO] Deleted junk scene NFO: {f}")
                except Exception as e:
                    log(f"  [WARN] Could not delete scene NFO: {f}: {e}")

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

def main():
    global shutdown_requested
    
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)
    # Filter out non-movie directories
    skip_dirs = {'failed', 'logs', 'scripts', 'saved', 'foreign', 'audiobooks', 'books', 'music', 'tvshows'}
    srcs = [os.path.join(SOURCE_DIR, d) for d in os.listdir(SOURCE_DIR) 
            if os.path.isdir(os.path.join(SOURCE_DIR, d)) and d not in skip_dirs]
    log(f"▶ Queued {len(srcs)} folders for cleaning with up to {MAX_WORKERS} workers")
    
    if srcs:
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                # Use as_completed instead of map for better interrupt handling
                futures = [pool.submit(clean_folder, src) for src in srcs]
                completed_count = 0
                
                try:
                    for future in as_completed(futures):
                        completed_count += 1
                        log(f"📊 Progress: {completed_count}/{len(futures)} folders completed")
                        
                        if shutdown_requested:
                            log("⚠️ Shutdown requested, cancelling remaining tasks...")
                            for f in futures:
                                f.cancel()
                            pool.shutdown(wait=False)
                            log("⚠️ Shutdown complete. Some folders may not have been processed.")
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
                    log("⚠️ Shutdown complete. Some folders may not have been processed.")
                    return
                    
        except KeyboardInterrupt:
            log("⚠️ Received interrupt signal during startup, exiting...")
            return
    
    log("All folders processed.")


if __name__ == "__main__":
    main()

