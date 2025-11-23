#!/usr/bin/python3
import subprocess
import re
import os
import shutil
import glob

# Source directory
SOURCE_DIR = "./"

# Subdirectories for categorization
DEST_DIRS = {
    "multi_vids": "./multi-vids",
    "multi_aud": "./multi-aud",
    "codec": "./codec",
    "subs": "./subs",
    "error": "./error",
}

# Ensure destination directories exist
for dir in DEST_DIRS.values():
    os.makedirs(dir, exist_ok=True)

# Get all MKV files in the source directory
mkv_files = glob.glob(os.path.join(SOURCE_DIR, "*.mkv"))

def move_file(file, destination):
    """Move a file to a specific directory."""
    shutil.move(file, os.path.join(destination, os.path.basename(file)))
    print(f"Moved {file} to {destination}")

def process_mkv(file):
    """Process a single MKV file and categorize it."""
    try:
        # Run mkvinfo to extract track information
        result = subprocess.run(["mkvinfo", file], capture_output=True, text=True, check=True)
        output = result.stdout.splitlines()

        video_track_count = 0
        audio_track_count = 0
        audio_languages = []
        audio_codecs = []
        has_subtitles = False

        in_tracks_section = False
        track_type = None
        language = "N/A"
        codec_id = "N/A"

        for line in output:
            line = line.strip()

            # Detect start of tracks section
            if "|+ Tracks" in line:
                in_tracks_section = True

            # Detect start of a track
            elif in_tracks_section and "| + Track" in line:
                if track_type == "video":
                    video_track_count += 1
                elif track_type == "audio":
                    audio_track_count += 1
                    audio_languages.append(language.lower())
                    audio_codecs.append(codec_id)
                elif track_type == "subtitles":
                    has_subtitles = True
                
                # Reset for next track
                track_type = None
                language = "N/A"
                codec_id = "N/A"

            # Track type
            elif "Track type:" in line:
                track_type = re.search(r'Track type: (\w+)', line).group(1)

            # Language
            elif "Language (IETF BCP 47):" in line:
                language = line.split(":")[-1].strip()

            # Codec ID
            elif "Codec ID:" in line and track_type == "audio":
                codec_id = line.split(":")[-1].strip()

        # Final processing of last track
        if track_type == "audio":
            audio_track_count += 1
            audio_languages.append(language.lower())
            audio_codecs.append(codec_id)

        # Categorize the file
        if video_track_count > 1:
            move_file(file, DEST_DIRS["multi_vids"])
        elif audio_track_count > 1 or not any(lang in ["en", "eng"] for lang in audio_languages):
            move_file(file, DEST_DIRS["multi_aud"])
        elif not all(codec_id for codec_id in audio_codecs):
            move_file(file, DEST_DIRS["codec"])
        elif has_subtitles:
            move_file(file, DEST_DIRS["subs"])

    except subprocess.CalledProcessError as e:
        print(f"Error processing {file}: {e}")
        move_file(file, DEST_DIRS["error"])

# Process each MKV file
for mkv_file in mkv_files:
    process_mkv(mkv_file)

print("\nProcessing completed.")

