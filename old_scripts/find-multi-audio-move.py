#!/usr/bin/python3
import subprocess
import re
import os
import shutil
import glob

# Process all MKV files in the current directory
mkv_files = glob.glob("./*.mkv")

def extract_mkv_tracks(file):
    try:
        # Run mkvinfo command to extract track information
        result = subprocess.run(["mkvinfo", file], capture_output=True, text=True, check=True)
        output = result.stdout.splitlines()

        print(f"\nProcessing: {file}")
        print("-" * 50)

        in_tracks_section = False
        track_number = None
        track_type = None
        language = "N/A"
        codec_id = "N/A"

        video_track_count = 0
        audio_track_count = 0

        for line in output:
            line = line.strip()

            # Detect start of the tracks section
            if "|+ Tracks" in line:
                in_tracks_section = True

            # Detect start of a specific track
            elif in_tracks_section and "| + Track" in line:
                if track_number is not None:
                    print(f"Track #{track_number} | Type: {track_type} | Language: {language} | Codec ID: {codec_id}")
                track_number = None
                track_type = None
                language = "N/A"
                codec_id = "N/A"

            # Detect track number
            elif "Track number:" in line:
                track_number = re.search(r'Track number: (\d+)', line).group(1)

            # Detect track type
            elif "Track type:" in line:
                track_type = re.search(r'Track type: (\w+)', line).group(1)
                if track_type == "video":
                    video_track_count += 1
                elif track_type == "audio":
                    audio_track_count += 1

            # Detect language
            elif "Language (IETF BCP 47):" in line:
                language = line.split(":")[-1].strip()

            # Detect Codec ID for audio tracks
            elif "Codec ID:" in line and track_type == "audio":
                codec_id = line.split(":")[-1].strip()

        # If more than one video track, move file and skip further processing
        if video_track_count > 1:
            os.makedirs("./mkv_multi_videos", exist_ok=True)
            shutil.move(file, f"./mkv_multi_videos/{os.path.basename(file)}")
            print(f"Moved {file} to ./mkv_multi_videos due to multiple video tracks.")
            return

        # If more than one audio track, move file to ./review folder
        if audio_track_count > 1:
            os.makedirs("./review", exist_ok=True)
            shutil.move(file, f"./review/{os.path.basename(file)}")
            print(f"Moved {file} to ./review due to multiple audio tracks.")
            return

        # Print the last track
        if track_number is not None:
            print(f"Track #{track_number} | Type: {track_type} | Language: {language} | Codec ID: {codec_id}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {file}: {e}")

# Process each MKV file
for mkv_file in mkv_files:
    extract_mkv_tracks(mkv_file)

print("\nTrack listing completed.")

