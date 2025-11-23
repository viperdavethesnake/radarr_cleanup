#!/usr/bin/python3

import os
import subprocess

def get_tracks_info(mkv_file):
    """Get track information for an MKV file using mkvmerge."""
    try:
        result = subprocess.run(
            ['mkvmerge', '-i', mkv_file],
            capture_output=True,
            text=True,
            check=True
        )
        tracks = []
        for line in result.stdout.splitlines():
            if line.startswith("Track ID"):
                parts = line.split(':', 1)
                track_id = parts[0].split()[-1]
                track_info = parts[1].strip()
                tracks.append((track_id, track_info))
        return tracks
    except subprocess.CalledProcessError as e:
        print(f"Error reading tracks from {mkv_file}: {e}")
        return []

def delete_tracks(mkv_file, exclude_track_ids):
    """Delete specified tracks from an MKV file using mkvmerge."""
    output_file = mkv_file.replace('.mkv', '_edited.mkv')

    # Get all tracks and construct include list
    all_tracks = get_tracks_info(mkv_file)
    include_tracks = [
        f'{track_type}:{track_id}'
        for track_id, track_info in all_tracks
        if track_id not in exclude_track_ids
        for track_type in ['video', 'audio', 'subtitles']
        if track_type in track_info.lower()
    ]

    try:
        # Construct the mkvmerge command
        command = ['mkvmerge', '-o', output_file]
        for include_track in include_tracks:
            command.extend(['--track', include_track])
        command.append(mkv_file)

        subprocess.run(command, check=True)
        print(f"Tracks removed successfully! Edited file saved as: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error while deleting tracks from {mkv_file}: {e}")

def main():
    directory = input("Enter the directory to scan for MKV files: ").strip()
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist.")
        return

    mkv_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.mkv')]
    if not mkv_files:
        print("No MKV files found in the specified directory.")
        return

    for mkv_file in mkv_files:
        print(f"\nAnalyzing {mkv_file}...")
        tracks = get_tracks_info(mkv_file)
        if len(tracks) > 2:  # More than one video and one audio track
            print(f"File '{mkv_file}' has more than two tracks.")
            print("Tracks found:")
            for track_id, track_info in tracks:
                print(f"  Track ID {track_id}: {track_info}")

            delete_option = input("Do you want to delete specific tracks? (yes/no): ").strip().lower()
            if delete_option == 'yes':
                track_ids = input("Enter the Track IDs to delete (comma-separated): ").strip().split(',')
                track_ids = [tid.strip() for tid in track_ids]
                delete_tracks(mkv_file, track_ids)
        else:
            print(f"File '{mkv_file}' has only one video and one audio track. No action required.")

if __name__ == "__main__":
    main()

