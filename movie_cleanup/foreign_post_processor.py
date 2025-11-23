#!/usr/bin/env python3
 
"""
🌍 Foreign Post Processor - Language Standardization Tool

A modern Python 3.13 tool for processing foreign language movies with
IETF BCP 47 language code standardization and metadata validation.

Features:
- IETF BCP 47 language code standardization (ISO 639-1 format)
- Metadata cleanliness verification (no unwanted tags/attachments)
- Concurrent processing with progress tracking
- Simple copy operation for pre-processed foreign films
- Beautiful progress visualization and real-time statistics
"""

import os
import shutil
import subprocess
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path

FOREIGN_DIR = "/storage/media/servarr/foreign"
CLEANED_DIR = "/storage/media/servarr/cleaned"
LOG_DIR = './logs'
MAX_WORKERS = 4

# ========== MODERN STYLING =============
class Colors:
    """ANSI color codes for beautiful terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Status colors
    SUCCESS = '\033[92m'  # Bright green
    WARNING = '\033[93m'  # Bright yellow
    ERROR = '\033[91m'    # Bright red
    INFO = '\033[94m'     # Bright blue
    
    # Accent colors
    CYAN = '\033[96m'     # Bright cyan
    MAGENTA = '\033[95m'  # Bright magenta
    WHITE = '\033[97m'    # Bright white
    GRAY = '\033[90m'     # Dark gray

@dataclass
class ForeignStats:
    """Modern data class for tracking foreign processing statistics"""
    total_movies: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    language_updates: int = 0
    metadata_verified: int = 0
    start_time: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_movies == 0:
            return 0.0
        return (self.processed / self.total_movies) * 100
    
    def elapsed_time(self) -> float:
        """Get elapsed processing time"""
        return time.time() - self.start_time
    
    def processing_rate(self) -> float:
        """Calculate movies processed per minute"""
        elapsed = self.elapsed_time()
        if elapsed == 0:
            return 0.0
        return (self.processed / elapsed) * 60

# Global state
stats = ForeignStats()

def log(msg: str) -> None:
    """Enhanced logging with timestamp and color support"""
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    Path(LOG_DIR).mkdir(exist_ok=True)
    with open(Path(LOG_DIR) / 'foreign_post_processor_debug.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def print_status(status: str, movie: str, details: str = "") -> None:
    """Print colorized status messages for foreign movie processing"""
    status_icons = {
        'PROCESSING': f"{Colors.INFO}🔍{Colors.RESET}",
        'SUCCESS': f"{Colors.SUCCESS}✅{Colors.RESET}",
        'FAILED': f"{Colors.ERROR}❌{Colors.RESET}",
        'SKIPPED': f"{Colors.WARNING}⏭️{Colors.RESET}",
        'LANGUAGE': f"{Colors.CYAN}🌍{Colors.RESET}",
        'METADATA': f"{Colors.MAGENTA}📋{Colors.RESET}",
        'COPYING': f"{Colors.INFO}📁{Colors.RESET}",
    }
    
    icon = status_icons.get(status, "❓")
    color = getattr(Colors, status, Colors.RESET) if hasattr(Colors, status) else Colors.RESET
    
    # Truncate long movie names for better display
    display_movie = movie[:50] + "..." if len(movie) > 53 else movie
    
    print(f"{icon} {color}{display_movie}{Colors.RESET}", end="")
    if details:
        print(f" {Colors.DIM}({details}){Colors.RESET}")
    else:
        print()

def print_progress() -> None:
    """Print a beautiful progress bar with real-time statistics"""
    if stats.total_movies == 0:
        return
        
    percent = stats.success_rate()
    elapsed = stats.elapsed_time()
    rate = stats.processing_rate()
    eta = (stats.total_movies - stats.processed) / (stats.processed / elapsed) if stats.processed > 0 and elapsed > 0 else 0
    
    # Progress bar
    bar_length = 30
    filled = int(bar_length * stats.processed // stats.total_movies)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    # Color coding based on success rate
    if percent >= 90:
        rate_color = Colors.SUCCESS
    elif percent >= 75:
        rate_color = Colors.WARNING
    else:
        rate_color = Colors.ERROR
    
    print(f"\r{Colors.CYAN}Progress: {Colors.RESET}"
          f"{Colors.WHITE}[{bar}] {Colors.RESET}"
          f"{Colors.BOLD}{percent:5.1f}%{Colors.RESET} "
          f"{Colors.DIM}({stats.processed}/{stats.total_movies}) "
          f"Rate: {rate:.1f}/min "
          f"ETA: {eta/60:.1f}m "
          f"Lang: {stats.language_updates} "
          f"Meta: {stats.metadata_verified}{Colors.RESET}", end="", flush=True)

def print_summary() -> None:
    """Print a beautiful summary report"""
    elapsed = stats.elapsed_time()
    success_rate = stats.success_rate()
    
    # Beautiful header
    print(f"\n{Colors.BOLD}{Colors.WHITE}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}📊 FOREIGN PROCESSING SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE}{'═' * 60}{Colors.RESET}")
    
    # Stats with colors
    print(f"{Colors.INFO}📁 Total movies:{Colors.RESET} {Colors.BOLD}{stats.total_movies}{Colors.RESET}")
    print(f"{Colors.SUCCESS}✅ Processed:{Colors.RESET} {Colors.BOLD}{stats.processed}{Colors.RESET}")
    print(f"{Colors.ERROR}❌ Failed:{Colors.RESET} {Colors.BOLD}{stats.failed}{Colors.RESET}")
    print(f"{Colors.WARNING}⏭️ Skipped:{Colors.RESET} {Colors.BOLD}{stats.skipped}{Colors.RESET}")
    print(f"{Colors.CYAN}🌍 Language updates:{Colors.RESET} {Colors.BOLD}{stats.language_updates}{Colors.RESET}")
    print(f"{Colors.MAGENTA}📋 Metadata verified:{Colors.RESET} {Colors.BOLD}{stats.metadata_verified}{Colors.RESET}")
    
    # Success rate with color coding
    if success_rate >= 90:
        rate_color = Colors.SUCCESS
    elif success_rate >= 75:
        rate_color = Colors.WARNING
    else:
        rate_color = Colors.ERROR
        
    print(f"{Colors.INFO}🎯 Success rate:{Colors.RESET} {rate_color}{Colors.BOLD}{success_rate:.1f}%{Colors.RESET}")
    print(f"{Colors.INFO}⏱️ Total time:{Colors.RESET} {Colors.BOLD}{elapsed/60:.1f} minutes{Colors.RESET}")
    print(f"{Colors.INFO}📈 Processing rate:{Colors.RESET} {Colors.BOLD}{stats.processing_rate():.1f} movies/minute{Colors.RESET}")
    
    # Visual progress bar for success rate
    bar_length = 40
    filled = int(bar_length * success_rate / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"{Colors.INFO}📊 Progress:{Colors.RESET} {rate_color}[{bar}]{Colors.RESET}")
    
    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")

def fast_copy(src: str, dst: str) -> None:
    """Copy file with fallback options for different filesystems"""
    log(f"    [COPY] Starting copy: {os.path.basename(src)}")
    try:
        # Try reflink first (for Btrfs/ZFS)
        subprocess.run(['cp', '--reflink=auto', src, dst], check=True, timeout=600)  # 10 minute timeout
        log(f"    [COPY] Reflink copy completed successfully")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log(f"    [COPY] Reflink failed, trying regular copy: {e}")
        try:
            # Fallback to regular copy
            subprocess.run(['cp', src, dst], check=True, timeout=600)  # 10 minute timeout
            log(f"    [COPY] Regular copy completed successfully")
        except subprocess.CalledProcessError as e:
            log(f"    [COPY] Regular copy failed, using shutil: {e}")
            # Final fallback using shutil
            shutil.copy2(src, dst)
            log(f"    [COPY] Shutil copy completed successfully")

def find_main_mkv(folder):
    for f in os.listdir(folder):
        if f.lower().endswith('.mkv'):
            return f
    return None

def standardize_language_tags(mkv_path: str) -> int:
    """Ensure all tracks have proper IETF BCP 47 language codes"""
    global stats
    
    # Language mapping for common cases (ISO 639-2 to ISO 639-1)
    lang_map = {
        'eng': 'en', 'jpn': 'ja', 'ita': 'it', 'spa': 'es', 
        'fra': 'fr', 'deu': 'de', 'rus': 'ru', 'chi': 'zh',
        'kor': 'ko', 'por': 'pt', 'nld': 'nl', 'swe': 'sv',
        'dan': 'da', 'fin': 'fi', 'nor': 'no', 'pol': 'pl',
        'tur': 'tr', 'ara': 'ar', 'heb': 'he', 'hin': 'hi'
    }
    
    updates = 0
    
    # Get current track info
    result = subprocess.run(['mkvmerge', '-J', mkv_path], 
                          capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    
    # Build mkvpropedit commands for language standardization
    for track in info.get('tracks', []):
        track_id = track['id']
        track_type = track['type']
        old_lang = track['properties'].get('language', '')
        
        # Only process audio and subtitle tracks (video tracks don't have language)
        if track_type in ['audio', 'subtitles'] and old_lang in lang_map:
            new_lang = lang_map[old_lang]
            cmd = ['mkvpropedit', mkv_path, '--edit', f'track:{track_id}', 
                   '--set', f'language={new_lang}']
            try:
                subprocess.run(cmd, check=True, timeout=60)
                log(f"    [LANG] Track {track_id} ({track_type}): {old_lang} → {new_lang}")
                updates += 1
            except subprocess.CalledProcessError as e:
                log(f"    [WARN] Failed to set language for track {track_id}: {e}")
                # Continue processing other tracks
    
    stats.language_updates += updates
    return updates

def verify_clean_metadata(mkv_path: str) -> bool:
    """Verify no unwanted tags or attachments"""
    global stats
    
    result = subprocess.run(['mkvmerge', '-J', mkv_path], 
                          capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    
    is_clean = True
    
    # Check for global tags
    if info.get('tags'):
        log(f"⚠️  Warning: {os.path.basename(mkv_path)} has global tags")
        is_clean = False
    
    # Check for attachments  
    if info.get('attachments'):
        log(f"⚠️  Warning: {os.path.basename(mkv_path)} has attachments")
        is_clean = False
    
    if is_clean:
        stats.metadata_verified += 1
        
    return is_clean

def process_foreign_folder(foreign_folder: str) -> None:
    """Process a single foreign movie folder with beautiful status updates"""
    global stats
    
    base = os.path.basename(foreign_folder)
    print_status('PROCESSING', base)
    
    try:
        t0 = time.perf_counter()
        
        # Find MKV file
        mkv_file = find_main_mkv(foreign_folder)
        if not mkv_file:
            raise Exception(f"No MKV file found in {foreign_folder}")
        
        src_mkv = os.path.join(foreign_folder, mkv_file)
        dst_folder = os.path.join(CLEANED_DIR, base)
        
        # Remove destination folder if it exists to avoid conflicts
        if os.path.exists(dst_folder):
            shutil.rmtree(dst_folder)
        
        os.makedirs(dst_folder, exist_ok=True)
        dst_mkv = os.path.join(dst_folder, mkv_file)

        # Standardize language tags
        print_status('LANGUAGE', base, "Standardizing language codes")
        lang_updates = standardize_language_tags(src_mkv)
        if lang_updates > 0:
            print_status('LANGUAGE', base, f"Updated {lang_updates} tracks")

        # Verify clean metadata
        print_status('METADATA', base, "Verifying metadata")
        is_clean = verify_clean_metadata(src_mkv)
        if not is_clean:
            print_status('WARNING', base, "Metadata issues detected")
        
        # Copy MKV to destination (preserving exact filename)
        print_status('COPYING', base, "Copying MKV file")
        try:
            fast_copy(src_mkv, dst_mkv)
        except Exception as copy_error:
            log(f"    [COPY] Copy failed: {copy_error}")
            raise

        # Copy metadata files
        for fname in ['movie.nfo', 'poster.jpg']:
            src_file = os.path.join(foreign_folder, fname)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(dst_folder, fname))

        # Success completion
        elapsed = time.perf_counter() - t0
        print_status('SUCCESS', base, f"Completed in {elapsed:.1f}s")
        stats.processed += 1
    except Exception as e:
        print_status('FAILED', base, f"Error: {str(e)[:50]}")
        stats.failed += 1
        log(f"❌ ERROR processing {base}: {e}\n{traceback.format_exc()}")
        # Clean up failed output
        try:
            if os.path.isdir(dst_folder):
                shutil.rmtree(dst_folder, ignore_errors=True)
        except Exception as e2:
            log(f"❌ Secondary cleanup failed: {e2}")

def main() -> None:
    """Main function with beautiful progress tracking and modern UX"""
    global stats
    
    # Print beautiful header
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}🌍 Foreign Post Processor{Colors.RESET}")
    print(f"{Colors.DIM}━{'━' * 50}{Colors.RESET}")
    print(f"{Colors.INFO}📁 Source:{Colors.RESET} {FOREIGN_DIR}")
    print(f"{Colors.INFO}📂 Destination:{Colors.RESET} {CLEANED_DIR}")
    print(f"{Colors.INFO}🧵 Workers:{Colors.RESET} {MAX_WORKERS}")
    print(f"{Colors.INFO}🔧 MKVToolNix:{Colors.RESET} {'✅ Available' if shutil.which('mkvpropedit') else '❌ Missing'}")
    print(f"{Colors.DIM}━{'━' * 50}{Colors.RESET}\n")
    
    # Initialize directories
    Path(LOG_DIR).mkdir(exist_ok=True)
    Path(CLEANED_DIR).mkdir(exist_ok=True)
    
    # Get folders to process
    if not Path(FOREIGN_DIR).exists():
        print(f"{Colors.ERROR}❌ Source directory '{FOREIGN_DIR}' does not exist{Colors.RESET}")
        return
    
    folders = [os.path.join(FOREIGN_DIR, d) for d in os.listdir(FOREIGN_DIR)
               if os.path.isdir(os.path.join(FOREIGN_DIR, d))]
    
    # Initialize stats
    stats.total_movies = len(folders)
    stats.start_time = time.time()
    
    if not folders:
        print(f"{Colors.WARNING}⚠️ No foreign movie folders found in {FOREIGN_DIR}{Colors.RESET}")
        return
    
    print(f"{Colors.INFO}📂 Found {len(folders)} foreign movie folders to process{Colors.RESET}\n")
    
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(process_foreign_folder, folder) for folder in folders]
            completed_count = 0
            
            try:
                for future in as_completed(futures):
                    completed_count += 1
                    
                    # Update progress bar
                    print_progress()
                    
                    try:
                        future.result(timeout=300)  # 5 minute timeout per future
                    except Exception as e:
                        print(f"\n{Colors.ERROR}❌ Worker thread error: {e}{Colors.RESET}")
                        
            except KeyboardInterrupt:
                print(f"\n{Colors.WARNING}⚠️ Received interrupt signal, shutting down gracefully...{Colors.RESET}")
                for f in futures:
                    f.cancel()
                pool.shutdown(wait=False)
                print(f"{Colors.WARNING}⚠️ Shutdown complete. Some folders may not have been processed.{Colors.RESET}")
                
    except KeyboardInterrupt:
        print(f"{Colors.WARNING}⚠️ Received interrupt signal during startup, exiting...{Colors.RESET}")
        return
    
    # Clear progress line and print summary
    print()  # New line after progress bar
    print_summary()

if __name__ == "__main__":
    main() 