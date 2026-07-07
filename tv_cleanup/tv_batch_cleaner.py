#!/usr/bin/env python3

import os, shutil, time, traceback, json, subprocess, re, signal, tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from xml.etree.ElementTree import Element, SubElement, ElementTree
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIG =============
SOURCE_DIR = './tvshows'
DEST_DIR = './tagged_tv'
REVIEW_DIR = './review_tv'
FAILED_DIR = './failed_tv'
LOG_DIR = './logs'
MAX_WORKERS = 8
TMDB_API_KEY = os.getenv('TMDB_API_KEY', 'your_api_key_here')

TVDB_RE = re.compile(r'tvdbid-(\d+)', re.IGNORECASE)
IMDB_RE = re.compile(r'tt\d{6,9}')
SE_RE = re.compile(r'[Ss](\d{1,2})[Ee](\d{1,3})')
SEASON_DIR_RE = re.compile(r'(?:season|s)[\s_]*(\d{1,2})$', re.IGNORECASE)
VIDEO_EXTS = ('.mkv', '.mp4')

shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    log("⚠️ Interrupt signal received, initiating graceful shutdown...")
    import threading
    def force_exit():
        time.sleep(3)
        log("⚠️ Force exiting due to multiple interrupts...")
        os._exit(1)
    threading.Thread(target=force_exit, daemon=True).start()


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
    subprocess.run(['cp', '--reflink=auto', src, dst], check=True, timeout=600)


def convert_mp4_to_mkv(src, dst):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', src,
        '-map', '0:v', '-map', '0:a',
        '-c', 'copy',
        '-map_chapters', '-1',
        dst,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=900, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        log(f"  [ERR] ffmpeg failed: {(e.stderr or '').strip()[:500]}")
        raise


def find_show_id(folder):
    """Return (kind, id) where kind is 'tvdb' or 'imdb'. Sonarr embeds [tvdbid-N] in folder names."""
    base = os.path.basename(folder)
    m = TVDB_RE.search(base)
    if m:
        return ('tvdb', m.group(1))
    m = IMDB_RE.search(base)
    if m:
        return ('imdb', m.group(0))

    nfo = os.path.join(folder, 'tvshow.nfo')
    if os.path.isfile(nfo):
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(nfo)
            for uid in tree.getroot().findall('uniqueid'):
                t = (uid.get('type') or '').lower()
                if t == 'tvdb' and uid.text:
                    return ('tvdb', uid.text.strip())
                if t == 'imdb' and uid.text:
                    m = IMDB_RE.match(uid.text.strip())
                    if m:
                        return ('imdb', m.group(0))
        except Exception:
            pass
    return (None, None)


def fetch_tmdb_show(kind, ext_id):
    """Look up show by TVDB or IMDb id; return (meta, poster_url, fanart_url, imdb_id, tvdb_id)."""
    src_param = 'tvdb_id' if kind == 'tvdb' else 'imdb_id'
    url = (f'https://api.themoviedb.org/3/find/{ext_id}'
           f'?api_key={TMDB_API_KEY}&external_source={src_param}')
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = data.get('tv_results') or []
    if not results:
        raise Exception(f"TMDB lookup failed for {kind}={ext_id}")
    tmdb_id = results[0]['id']

    url = (f'https://api.themoviedb.org/3/tv/{tmdb_id}'
           f'?api_key={TMDB_API_KEY}&append_to_response=credits,external_ids,content_ratings')
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    meta = resp.json()

    ext = meta.get('external_ids') or {}
    imdb_id = ext.get('imdb_id') or (ext_id if kind == 'imdb' else None)
    tvdb_val = ext.get('tvdb_id')
    tvdb_id = str(tvdb_val) if tvdb_val else (ext_id if kind == 'tvdb' else None)

    poster_url = ('https://image.tmdb.org/t/p/original' + meta['poster_path']) if meta.get('poster_path') else ''
    fanart_url = ('https://image.tmdb.org/t/p/original' + meta['backdrop_path']) if meta.get('backdrop_path') else ''
    return meta, poster_url, fanart_url, imdb_id, tvdb_id


def fetch_tmdb_season(tmdb_id, season_num):
    url = (f'https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_num}'
           f'?api_key={TMDB_API_KEY}')
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def download_image(url, dest):
    if not url:
        return
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)


def strip_attachments(mkvfile):
    result = subprocess.run(['mkvmerge', '-J', mkvfile],
                            capture_output=True, text=True, check=True, timeout=30)
    info = json.loads(result.stdout)
    attachments = info.get('attachments', [])
    if not attachments:
        return
    cmd = ['mkvpropedit', mkvfile]
    for att in attachments:
        uid = (att.get('properties') or {}).get('uid')
        if uid is not None:
            cmd += ['--delete-attachment', f'={uid}']
    if len(cmd) > 2:
        subprocess.run(cmd, check=True, timeout=60)


def write_json(meta, dest):
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def pick_us_content_rating(meta):
    for r in (meta.get('content_ratings') or {}).get('results', []):
        if r.get('iso_3166_1') == 'US' and r.get('rating'):
            return r['rating']
    return ''


def sort_title(title):
    for article in ('The ', 'A ', 'An '):
        if title.startswith(article):
            return f"{title[len(article):]}, {article.strip()}"
    return title


def write_tvshow_nfo(meta, imdb_id, tvdb_id, dest):
    root = Element('tvshow')

    def safe_sub(parent, tag, val):
        if val:
            SubElement(parent, tag).text = val if isinstance(val, str) else str(val)

    title = meta.get('name')
    safe_sub(root, 'title', title)
    safe_sub(root, 'originaltitle', meta.get('original_name'))
    safe_sub(root, 'showtitle', title)
    if title:
        safe_sub(root, 'sorttitle', sort_title(title))
    safe_sub(root, 'plot', meta.get('overview'))
    safe_sub(root, 'outline', meta.get('overview'))
    safe_sub(root, 'premiered', meta.get('first_air_date'))
    if meta.get('first_air_date'):
        safe_sub(root, 'year', meta['first_air_date'][:4])
    safe_sub(root, 'status', meta.get('status'))
    runtime = meta.get('episode_run_time') or []
    if runtime:
        safe_sub(root, 'runtime', str(runtime[0]))
    safe_sub(root, 'mpaa', pick_us_content_rating(meta))
    safe_sub(root, 'rating', str(meta.get('vote_average', '')))
    safe_sub(root, 'votes', str(meta.get('vote_count', '')))
    safe_sub(root, 'tmdbid', str(meta.get('id')))
    safe_sub(root, 'imdbid', imdb_id)

    if meta.get('id'):
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'tmdb')
        uid.set('default', 'true')
        uid.text = str(meta['id'])
    if tvdb_id:
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'tvdb')
        uid.text = str(tvdb_id)
    if imdb_id:
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'imdb')
        uid.text = imdb_id

    for g in meta.get('genres', []):
        safe_sub(root, 'genre', g.get('name'))
    for net in meta.get('networks', []):
        safe_sub(root, 'studio', net.get('name'))
    for country in meta.get('production_countries', []):
        safe_sub(root, 'country', country.get('name'))

    for c in meta.get('created_by', []):
        safe_sub(root, 'credits', c.get('name'))

    for i, a in enumerate(meta.get('credits', {}).get('cast', [])[:15]):
        actor_el = SubElement(root, 'actor')
        safe_sub(actor_el, 'name', a.get('name'))
        safe_sub(actor_el, 'role', a.get('character'))
        safe_sub(actor_el, 'order', str(i))
        profile = a.get('profile_path')
        if profile:
            safe_sub(actor_el, 'thumb', f'https://image.tmdb.org/t/p/original{profile}')

    ElementTree(root).write(dest, encoding='utf-8', xml_declaration=True)


def write_episode_nfo(show_meta, ep_meta, imdb_id, tvdb_id, season_num, episode_num, dest):
    root = Element('episodedetails')

    def safe_sub(parent, tag, val):
        if val:
            SubElement(parent, tag).text = val if isinstance(val, str) else str(val)

    safe_sub(root, 'title', ep_meta.get('name'))
    safe_sub(root, 'showtitle', show_meta.get('name'))
    safe_sub(root, 'season', str(season_num))
    safe_sub(root, 'episode', str(episode_num))
    safe_sub(root, 'plot', ep_meta.get('overview'))
    safe_sub(root, 'aired', ep_meta.get('air_date'))
    if ep_meta.get('runtime'):
        safe_sub(root, 'runtime', str(ep_meta['runtime']))
    safe_sub(root, 'rating', str(ep_meta.get('vote_average', '')))
    safe_sub(root, 'votes', str(ep_meta.get('vote_count', '')))

    if ep_meta.get('id'):
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'tmdb')
        uid.set('default', 'true')
        uid.text = str(ep_meta['id'])
    if tvdb_id:
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'tvdb_show')
        uid.text = str(tvdb_id)
    if imdb_id:
        uid = SubElement(root, 'uniqueid')
        uid.set('type', 'imdb_show')
        uid.text = imdb_id

    for c in ep_meta.get('crew') or []:
        if c.get('job') == 'Director':
            safe_sub(root, 'director', c.get('name'))
        elif c.get('department') == 'Writing':
            safe_sub(root, 'credits', c.get('name'))

    guest_stars = (ep_meta.get('guest_stars') or [])[:10]
    for i, a in enumerate(guest_stars):
        actor_el = SubElement(root, 'actor')
        safe_sub(actor_el, 'name', a.get('name'))
        safe_sub(actor_el, 'role', a.get('character'))
        safe_sub(actor_el, 'order', str(i))
        profile = a.get('profile_path')
        if profile:
            safe_sub(actor_el, 'thumb', f'https://image.tmdb.org/t/p/original{profile}')

    ElementTree(root).write(dest, encoding='utf-8', xml_declaration=True)


def write_episode_tags_xml(show_meta, ep_meta, imdb_id, tvdb_id, season_num, episode_num, dest):
    """Per-episode tags.xml for mkvpropedit injection."""
    root = Element('Tags')

    show_tag = SubElement(root, 'Tag')
    targets = SubElement(show_tag, 'Targets')
    SubElement(targets, 'TargetTypeValue').text = '70'  # COLLECTION (show)

    show_pairs = [
        ('TITLE', show_meta.get('name') or ''),
        ('TMDB', str(show_meta.get('id') or '')),
        ('TVDB', str(tvdb_id or '')),
        ('IMDB', imdb_id or ''),
        ('GENRE', ', '.join([g['name'] for g in show_meta.get('genres', [])])),
        ('NETWORK', ', '.join([n['name'] for n in show_meta.get('networks', [])])),
    ]
    for k, v in show_pairs:
        if v:
            s = SubElement(show_tag, 'Simple')
            SubElement(s, 'Name').text = k
            SubElement(s, 'String').text = v

    ep_tag = SubElement(root, 'Tag')
    targets = SubElement(ep_tag, 'Targets')
    SubElement(targets, 'TargetTypeValue').text = '50'  # EPISODE

    ep_pairs = [
        ('TITLE', ep_meta.get('name') or ''),
        ('SEASON', str(season_num)),
        ('EPISODE', str(episode_num)),
        ('AIRED', ep_meta.get('air_date') or ''),
        ('PLOT', ep_meta.get('overview') or ''),
        ('TMDB_EPISODE', str(ep_meta.get('id') or '')),
    ]
    for k, v in ep_pairs:
        if v:
            s = SubElement(ep_tag, 'Simple')
            SubElement(s, 'Name').text = k
            SubElement(s, 'String').text = v

    ElementTree(root).write(dest, encoding='utf-8', xml_declaration=True)


def set_tags_in_mkv(mkvfile, tags_xml):
    subprocess.run(['mkvpropedit', mkvfile, '--tags', f'all:{tags_xml}'], check=True, timeout=60)


def _normalize_title_for_path(title):
    safe = re.sub(r'[\\/:*?"<>|]', '', title)
    safe = safe.replace(' ', '_').replace('.', '').strip()
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe


def show_folder_name(meta):
    title = meta.get('name') or 'Unknown_Show'
    year = (meta.get('first_air_date') or '')[:4]
    safe = _normalize_title_for_path(title)
    return f"{safe}_({year})" if year else safe


def episode_file_name(meta, ep_meta, season_num, episode_num, ext='.mkv'):
    show = _normalize_title_for_path(meta.get('name') or 'Unknown_Show')
    title = _normalize_title_for_path(ep_meta.get('name') or f'Episode_{episode_num}')
    return f"{show}_S{season_num:02d}E{episode_num:02d}_{title}{ext}"


def _move_to_failed(src_folder, base):
    failed = os.path.join(FAILED_DIR, base)
    try:
        if os.path.exists(failed):
            shutil.rmtree(failed, ignore_errors=True)
        shutil.move(src_folder, failed)
        log(f"  [FAILED] Moved to failed directory: {failed}")
    except Exception as e:
        log(f"❌ Could not move to failed: {e}")


def _find_videos(folder):
    """Walk show folder; return list of (season_num_or_None, video_path)."""
    out = []
    for root, dirs, files in os.walk(folder):
        season = None
        for part in os.path.relpath(root, folder).split(os.sep):
            m = SEASON_DIR_RE.match(part)
            if m:
                season = int(m.group(1))
                break
            if part.lower() in ('specials', 'season 0', 'season_0', 'season 00'):
                season = 0
                break
        for f in files:
            if not f.lower().endswith(VIDEO_EXTS):
                continue
            m = SE_RE.search(f)
            file_season = int(m.group(1)) if m else season
            out.append((file_season, os.path.join(root, f)))
    return out


def clean_show_folder(src_folder):
    global shutdown_requested
    if shutdown_requested:
        return

    base = os.path.basename(src_folder)
    log(f"\n▶ Processing: {base}")
    dst_show_folder = None
    try:
        t0 = time.perf_counter()

        kind, ext_id = find_show_id(src_folder)
        if not ext_id:
            log(f"❌ [SKIP] No TVDB/IMDb ID found in {base}. Moving to failed.")
            _move_to_failed(src_folder, base)
            return
        log(f"  [ID] {kind}={ext_id}")

        meta, poster_url, fanart_url, imdb_id, tvdb_id = timed(
            f"TMDB lookup for {kind}={ext_id}", fetch_tmdb_show, kind, ext_id)

        videos = _find_videos(src_folder)
        if not videos:
            log(f"❌ [SKIP] No video files in {base}")
            _move_to_failed(src_folder, base)
            return

        # Foreign-original shows are not handled by this pipeline — they are
        # managed by separate scripts / manual processes. Flag and fail them.
        if meta.get('original_language') != 'en':
            log(f"❌ [FAILED] Foreign original (original_language="
                f"{meta.get('original_language')}) — not handled here, moving to failed")
            _move_to_failed(src_folder, base)
            return

        new_base = show_folder_name(meta)
        dst_show_folder = os.path.join(DEST_DIR, new_base)
        os.makedirs(dst_show_folder, exist_ok=True)

        by_season = defaultdict(list)
        for season_num, vpath in videos:
            if season_num is None:
                log(f"  [WARN] Could not determine season for {vpath}; skipping")
                continue
            by_season[season_num].append(vpath)

        ep_total = sum(len(v) for v in by_season.values())
        ep_ok = 0
        ep_failed = 0
        seen_in_run = set()

        for season_num in sorted(by_season.keys()):
            if shutdown_requested:
                return
            season_meta = timed(
                f"TMDB season {season_num} for {meta.get('name')}",
                fetch_tmdb_season, meta['id'], season_num)
            episodes_by_num = {}
            if season_meta:
                for ep in season_meta.get('episodes') or []:
                    episodes_by_num[ep['episode_number']] = ep

            season_dir = os.path.join(dst_show_folder, f"Season {season_num:02d}")
            os.makedirs(season_dir, exist_ok=True)

            for vpath in by_season[season_num]:
                if shutdown_requested:
                    return
                fname = os.path.basename(vpath)
                m = SE_RE.search(fname)
                if not m:
                    log(f"  [WARN] No SxxExx in {fname}; skipping")
                    ep_failed += 1
                    continue
                episode_num = int(m.group(2))
                ep_meta = episodes_by_num.get(episode_num) or {
                    'name': f'Episode_{episode_num}',
                    'overview': '',
                    'air_date': '',
                    'id': None,
                }

                ep_filename = episode_file_name(meta, ep_meta, season_num, episode_num, '.mkv')
                dst_mkv = os.path.join(season_dir, ep_filename)

                if dst_mkv in seen_in_run:
                    log(f"  [WARN] In-run collision: {ep_filename} already produced; skipping {fname}")
                    ep_failed += 1
                    continue
                seen_in_run.add(dst_mkv)

                if os.path.isfile(dst_mkv) and os.path.getsize(dst_mkv) > 0:
                    log(f"  [SKIP] Output exists from prior run: {ep_filename}")
                    ep_ok += 1
                    continue

                try:
                    if vpath.lower().endswith('.mkv'):
                        timed(f"Copy MKV: {fname} → {ep_filename}", fast_copy, vpath, dst_mkv)
                    else:
                        timed(f"Convert MP4→MKV: {fname} → {ep_filename}", convert_mp4_to_mkv, vpath, dst_mkv)

                    timed(f"Strip attachments: {ep_filename}", strip_attachments, dst_mkv)

                    ep_nfo = os.path.splitext(dst_mkv)[0] + '.nfo'
                    timed(f"Write episode NFO: {os.path.basename(ep_nfo)}",
                          write_episode_nfo, meta, ep_meta, imdb_id, tvdb_id,
                          season_num, episode_num, ep_nfo)

                    tf = tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False)
                    tags_path = tf.name
                    tf.close()
                    try:
                        write_episode_tags_xml(meta, ep_meta, imdb_id, tvdb_id,
                                               season_num, episode_num, tags_path)
                        timed(f"Inject tags into MKV: {ep_filename}",
                              set_tags_in_mkv, dst_mkv, tags_path)
                    finally:
                        try:
                            os.remove(tags_path)
                        except Exception:
                            pass
                    ep_ok += 1
                except Exception as e:
                    log(f"  ❌ Episode failed: {fname}: {e}")
                    if os.path.isfile(dst_mkv):
                        try:
                            os.remove(dst_mkv)
                        except Exception:
                            pass
                    ep_failed += 1

        timed("Download poster", download_image, poster_url, os.path.join(dst_show_folder, "poster.jpg"))
        timed("Download fanart", download_image, fanart_url, os.path.join(dst_show_folder, "fanart.jpg"))
        timed("Write metadata.json", write_json, meta, os.path.join(dst_show_folder, "metadata.json"))
        timed("Write tvshow.nfo", write_tvshow_nfo, meta, imdb_id, tvdb_id,
              os.path.join(dst_show_folder, "tvshow.nfo"))

        if ep_failed == 0 and ep_ok == ep_total:
            timed(f"Delete original folder: {src_folder}", shutil.rmtree, src_folder)
            log(f"✔ [DONE] {base}: {ep_ok}/{ep_total} episodes, total {(time.perf_counter()-t0):.2f}s\n")
        else:
            log(f"⚠ [PARTIAL] {base}: {ep_ok}/{ep_total} ok, {ep_failed} failed; "
                f"source kept at {src_folder}\n")

    except Exception as e:
        log(f"❌ ERROR processing {base}: {e}\n{traceback.format_exc()}")
        # Relocate any partial cleaned output out of DEST_DIR (the library-staging
        # dir) so it only ever holds complete shows. Park it next to the source
        # under failed_tv/ for inspection rather than deleting — a late failure
        # (e.g. artwork download) can leave fully-remuxed episodes worth keeping.
        if dst_show_folder and os.path.isdir(dst_show_folder):
            partial_dest = os.path.join(FAILED_DIR, f"{base}_cleaned_partial")
            try:
                os.makedirs(FAILED_DIR, exist_ok=True)
                if os.path.exists(partial_dest):
                    shutil.rmtree(partial_dest, ignore_errors=True)
                shutil.move(dst_show_folder, partial_dest)
                log(f"  [FAILED] Partial cleaned output → {partial_dest}")
            except Exception as move_err:
                log(f"❌ Could not relocate partial output: {move_err}")
        if os.path.isdir(src_folder):
            _move_to_failed(src_folder, base)


def main():
    global shutdown_requested

    for d in (LOG_DIR, DEST_DIR, REVIEW_DIR, FAILED_DIR):
        os.makedirs(d, exist_ok=True)

    srcs = [os.path.join(SOURCE_DIR, d) for d in os.listdir(SOURCE_DIR)
            if os.path.isdir(os.path.join(SOURCE_DIR, d)) and not d.startswith('.')]
    log(f"▶ Queued {len(srcs)} TV shows for cleaning with up to {MAX_WORKERS} workers")

    if srcs:
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = [pool.submit(clean_show_folder, src) for src in srcs]
                completed = 0
                try:
                    for fut in as_completed(futures):
                        completed += 1
                        log(f"📊 Progress: {completed}/{len(futures)} TV shows completed")

                        if shutdown_requested:
                            log("⚠️ Shutdown requested, cancelling remaining tasks...")
                            for f in futures:
                                f.cancel()
                            pool.shutdown(wait=False)
                            return

                        try:
                            fut.result(timeout=3600)
                        except Exception as e:
                            log(f"❌ Worker thread error: {e}")
                            log(f"❌ Worker thread traceback: {traceback.format_exc()}")
                except KeyboardInterrupt:
                    log("⚠️ Received interrupt signal, shutting down gracefully...")
                    shutdown_requested = True
                    for f in futures:
                        f.cancel()
                    pool.shutdown(wait=False)
                    return
        except KeyboardInterrupt:
            log("⚠️ Received interrupt signal during startup, exiting...")
            return

    log("All TV shows processed.")


if __name__ == "__main__":
    main()
