#!/usr/bin/python3

import os
import subprocess
import glob
import json

# Directories for source and output
source_dir = "./"
cleaned_dir = "./mkv_cleaned"
notruehd_dir = "./mkv_audio_notruehd"

# Ensure output directories exist
os.makedirs(cleaned_dir, exist_ok=True)
os.makedirs(notruehd_dir, exist_ok=True)

# Process **all** MKV files in the current directory
mkv_files = glob.glob(os.path.join(source_dir, "*.mkv"))

if not mkv_files:
    print("No MKV files found in the current directory.")
    exit(0)

for file in mkv_files:
    print(f"\nProcessing: {file}")
    filename = os.path.basename(file)

    try:
        # Generate a track list using JSON output from mkvmerge
        track_info = subprocess.run(["mkvmerge", "-J", file], capture_output=True, text=True, check=True)
        tracks = json.loads(track_info.stdout)["tracks"]

        video_track = None
        truehd_audio_track = None

        # Identify the video and desired audio track
        for track in tracks:
            if track["type"] == "video" and video_track is None:
                video_track = track["id"]
            elif (track["type"] == "audio" and
                  track["properties"].get("codec_id") == "A_TRUEHD" and
                  track["properties"].get("language") in ["eng", "en"]):
                truehd_audio_track = track["id"]

        if video_track is None or truehd_audio_track is None:
            print(f"Moved {filename} to {notruehd_dir} due to missing English A_TRUEHD audio track.")
            os.rename(file, os.path.join(notruehd_dir, filename))
            continue

        # Display track selection for confirmation
        print(f"Selected Video Track: {video_track}")
        print(f"Selected A_TRUEHD English Audio Track: {truehd_audio_track}")

        # Build corrected mkvmerge command with subtitles, attachments, and global tags excluded
        output_file = os.path.join(cleaned_dir, filename)
        mkvmerge_command = [
            "mkvmerge", "-o", output_file,
            "--track-order", f"0:{video_track},0:{truehd_audio_track}",
            f"--video-tracks", f"{video_track}",
            f"--audio-tracks", f"{truehd_audio_track}",
            "--default-track", f"{video_track}:yes",
            "--default-track", f"{truehd_audio_track}:yes",
            "--no-subtitles",      # Exclude subtitles
            "--no-attachments",    # Exclude attachments
            "--no-global-tags",    # Exclude global tags
            file
        ]

        # Execute mkvmerge command
        subprocess.run(mkvmerge_command, check=True)

        # Delete original file only if successful
        os.remove(file)
        print(f"Successfully processed {filename} and moved it to {cleaned_dir}.")

    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error processing {filename}: {e}")
    except Exception as e:
        print(f"Unexpected error with {filename}: {e}")

print("\nBatch processing completed.")

