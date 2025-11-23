#!/usr/bin/python3

import os
import subprocess

# Function to run mkvinfo on a file and capture the output
def get_mkv_info(filename):
    try:
        result = subprocess.run(['mkvinfo', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"Error while processing {filename}: {e}")
    return None

# Function to check tracks in the MKV file and classify them
def review_tracks(mkv_file):
    mkv_info = get_mkv_info(mkv_file)
    if not mkv_info:
        return None

    video_tracks = 0
    audio_tracks = 0
    subtitle_tracks = 0
    other_tracks = []

    # Parse the mkvinfo output to count the tracks and other elements
    for line in mkv_info.splitlines():
        if "Track type: video" in line:
            video_tracks += 1
        elif "Track type: audio" in line:
            audio_tracks += 1
        elif "Track type: subtitles" in line:
            subtitle_tracks += 1
        elif "Attachment" in line or "Tag" in line:
            other_tracks.append(line)

    return video_tracks, audio_tracks, subtitle_tracks, other_tracks

# Function to print the results based on conditions
def review_mkv_files():
    directory = os.getcwd()
    mkv_files = [f for f in os.listdir(directory) if f.endswith('.mkv')]

    for mkv_file in mkv_files:
        video_tracks, audio_tracks, subtitle_tracks, other_tracks = review_tracks(mkv_file)

        # Show files with more than one video track
        if video_tracks > 1:
            print(f"[INFO] {mkv_file} has more than one video track ({video_tracks} tracks)")

        # Show files with more than one audio track
        if audio_tracks > 1:
            print(f"[INFO] {mkv_file} has more than one audio track ({audio_tracks} tracks)")

        # Show files with tags or attachments
        if other_tracks:
            print(f"[INFO] {mkv_file} has tags or attachments:")
            for track in other_tracks:
                print(f"  - {track}")

# Run the review
if __name__ == "__main__":
    review_mkv_files()

