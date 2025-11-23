#!/usr/bin/python3

import os
import subprocess
import glob
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Directories for source and output
source_dir = "./"
cleaned_dir = "/Volumes/movies_tmm"  # NFS Mounted Path on macOS
notruehd_dir = "./nodts"  # Local directory for non-compliant files

# Set the number of threads for parallel processing
MAX_THREADS = 4

# Ensure the local directory for rejected files exists
os.makedirs(notruehd_dir, exist_ok=True)

# Collect all MKV files in the current directory
mkv_files = glob.glob(os.path.join(source_dir, "*.mkv"))

if not mkv_files:
    print("No MKV files found in the current directory.")
    exit(0)


def process_mkv(file):
    """Process a single MKV file with mkvmerge and save to the NFS mount."""
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
                  track["properties"].get("codec_id") == "A_DTS" and
                  track["properties"].get("language") in ["eng", "en"]):
                truehd_audio_track = track["id"]

        # If no valid TrueHD audio track, move the file to the non-compliant directory
        if video_track is None or truehd_audio_track is None:
            print(f"Moved {filename} to {notruehd_dir} due to missing English A_DTS audio track.")
            os.rename(file, os.path.join(notruehd_dir, filename))
            return f"{filename} moved to {notruehd_dir} (no A_DTS audio)."

        # Display selected tracks for confirmation
        print(f"Selected Video Track: {video_track}")
        print(f"Selected A_DTS English Audio Track: {truehd_audio_track}")

        # Build mkvmerge command excluding subtitles, attachments, and global tags
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

        # Delete the original file after successful processing
        os.remove(file)
        return f"{filename} successfully processed and moved to {cleaned_dir} via NFS."

    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        return f"Error processing {filename}: {e}"
    except Exception as e:
        return f"Unexpected error with {filename}: {e}"


# Run the processing in parallel using ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = {executor.submit(process_mkv, file): file for file in mkv_files}
    for future in as_completed(futures):
        print(future.result())

print("\nBatch processing completed.")


