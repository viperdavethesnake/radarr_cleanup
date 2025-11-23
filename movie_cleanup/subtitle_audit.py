#!/usr/bin/env python3
"""
Subtitle Track Audit Script
Audits all movies in /storage/media/movies for subtitle tracks and their display settings
"""

import os
import json
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class SubtitleTrack:
    id: int
    language: str
    codec: str
    name: str
    default_flag: bool
    forced_flag: bool
    hearing_impaired: bool

@dataclass
class MovieAudit:
    movie_name: str
    file_path: str
    has_subtitles: bool
    subtitle_tracks: List[SubtitleTrack]
    default_subtitles: List[SubtitleTrack]
    forced_subtitles: List[SubtitleTrack]

def get_mkv_info(mkv_path: str) -> Optional[Dict]:
    """Get MKV track information using mkvmerge"""
    try:
        result = subprocess.run(
            ['mkvmerge', '-J', mkv_path], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"Error getting info for {mkv_path}: {e}")
        return None

def parse_subtitle_tracks(tracks: List[Dict]) -> List[SubtitleTrack]:
    """Parse subtitle tracks from MKV info"""
    subtitle_tracks = []
    
    for track in tracks:
        if track.get('type') == 'subtitles':
            properties = track.get('properties', {})
            
            subtitle_track = SubtitleTrack(
                id=track.get('id', 0),
                language=properties.get('language', 'und'),
                codec=properties.get('codec_id', 'unknown'),
                name=properties.get('track_name', ''),
                default_flag=properties.get('flag_default', False),
                forced_flag=properties.get('flag_forced', False),
                hearing_impaired=properties.get('flag_hearing_impaired', False)
            )
            subtitle_tracks.append(subtitle_track)
    
    return subtitle_tracks

def audit_movie(movie_path: str) -> MovieAudit:
    """Audit a single movie for subtitle tracks"""
    movie_name = Path(movie_path).name
    mkv_file = None
    
    # Find MKV file
    for file in os.listdir(movie_path):
        if file.lower().endswith('.mkv'):
            mkv_file = os.path.join(movie_path, file)
            break
    
    if not mkv_file:
        return MovieAudit(
            movie_name=movie_name,
            file_path=movie_path,
            has_subtitles=False,
            subtitle_tracks=[],
            default_subtitles=[],
            forced_subtitles=[]
        )
    
    # Get MKV info
    mkv_info = get_mkv_info(mkv_file)
    if not mkv_info:
        return MovieAudit(
            movie_name=movie_name,
            file_path=mkv_file,
            has_subtitles=False,
            subtitle_tracks=[],
            default_subtitles=[],
            forced_subtitles=[]
        )
    
    tracks = mkv_info.get('tracks', [])
    subtitle_tracks = parse_subtitle_tracks(tracks)
    
    default_subtitles = [t for t in subtitle_tracks if t.default_flag]
    forced_subtitles = [t for t in subtitle_tracks if t.forced_flag]
    
    return MovieAudit(
        movie_name=movie_name,
        file_path=mkv_file,
        has_subtitles=len(subtitle_tracks) > 0,
        subtitle_tracks=subtitle_tracks,
        default_subtitles=default_subtitles,
        forced_subtitles=forced_subtitles
    )

def main():
    """Main audit function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Audit subtitle tracks in MKV movies')
    parser.add_argument('--path', '-p', default='/storage/media/movies', 
                       help='Path to movies directory (default: /storage/media/movies)')
    parser.add_argument('--threads', '-t', type=int, default=8,
                       help='Number of worker threads (default: 8)')
    parser.add_argument('--output', '-o', default='subtitle_audit_report.txt',
                       help='Output report file (default: subtitle_audit_report.txt)')
    args = parser.parse_args()
    
    # Configuration
    MOVIES_DIR = args.path
    MAX_WORKERS = args.threads
    REPORT_FILE = args.output
    
    movies = []
    
    print("🎬 Subtitle Track Audit")
    print("=" * 50)
    print(f"📁 Movies directory: {MOVIES_DIR}")
    print(f"🧵 Worker threads: {MAX_WORKERS}")
    print(f"📄 Report file: {REPORT_FILE}")
    print("=" * 50)
    
    # Get all movie directories
    movie_dirs = [d for d in os.listdir(MOVIES_DIR) 
                  if os.path.isdir(os.path.join(MOVIES_DIR, d))]
    
    print(f"Found {len(movie_dirs)} movies to audit...")
    print(f"Using {MAX_WORKERS} worker threads")
    print()
    
    # Audit each movie
    for i, movie_dir in enumerate(sorted(movie_dirs), 1):
        movie_path = os.path.join(MOVIES_DIR, movie_dir)
        print(f"[{i:3d}/{len(movie_dirs)}] Auditing: {movie_dir}")
        
        try:
            audit = audit_movie(movie_path)
            movies.append(audit)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    # Generate summary report
    print("\n" + "=" * 50)
    print("📊 AUDIT SUMMARY REPORT")
    print("=" * 50)
    
    total_movies = len(movies)
    movies_with_subtitles = sum(1 for m in movies if m.has_subtitles)
    movies_with_default_subs = sum(1 for m in movies if m.default_subtitles)
    movies_with_forced_subs = sum(1 for m in movies if m.forced_subtitles)
    
    print(f"📁 Total movies: {total_movies}")
    print(f"🎬 Movies with subtitles: {movies_with_subtitles}")
    print(f"⚠️  Movies with DEFAULT subtitles: {movies_with_default_subs}")
    print(f"🔒 Movies with FORCED subtitles: {movies_with_forced_subs}")
    print()
    
    # Detailed report for movies with default/forced subtitles
    if movies_with_default_subs > 0:
        print("⚠️  MOVIES WITH DEFAULT SUBTITLES (NEEDS ATTENTION):")
        print("-" * 50)
        for movie in movies:
            if movie.default_subtitles:
                print(f"  • {movie.movie_name}")
                for sub in movie.default_subtitles:
                    print(f"    - Track {sub.id}: {sub.language} ({sub.codec}) - {sub.name}")
        print()
    
    if movies_with_forced_subs > 0:
        print("🔒 MOVIES WITH FORCED SUBTITLES:")
        print("-" * 50)
        for movie in movies:
            if movie.forced_subtitles:
                print(f"  • {movie.movie_name}")
                for sub in movie.forced_subtitles:
                    print(f"    - Track {sub.id}: {sub.language} ({sub.codec}) - {sub.name}")
        print()
    
    # Movies without subtitles
    movies_without_subs = [m for m in movies if not m.has_subtitles]
    if movies_without_subs:
        print("❌ MOVIES WITHOUT SUBTITLES:")
        print("-" * 50)
        for movie in movies_without_subs:
            print(f"  • {movie.movie_name}")
        print()
    
    # Save detailed report to file
    with open(REPORT_FILE, 'w') as f:
        f.write("DETAILED SUBTITLE AUDIT REPORT\n")
        f.write("=" * 50 + "\n\n")
        
        for movie in movies:
            f.write(f"Movie: {movie.movie_name}\n")
            f.write(f"File: {movie.file_path}\n")
            f.write(f"Has subtitles: {movie.has_subtitles}\n")
            
            if movie.subtitle_tracks:
                f.write("Subtitle tracks:\n")
                for sub in movie.subtitle_tracks:
                    f.write(f"  - Track {sub.id}: {sub.language} ({sub.codec})\n")
                    f.write(f"    Name: {sub.name}\n")
                    f.write(f"    Default: {sub.default_flag}, Forced: {sub.forced_flag}, HI: {sub.hearing_impaired}\n")
            else:
                f.write("  No subtitle tracks found\n")
            f.write("\n")
    
    print(f"📄 Detailed report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
