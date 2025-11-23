#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import subprocess
import re

OUTPUT_FILE = "audio_tracks_report.txt"

def clean_movies(source_dir, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    with open(OUTPUT_FILE, "w") as report:
        for file in os.listdir(source_dir):
            if file.endswith(".mkv"):
                file_path = os.path.join(source_dir, file)
                new_file_path = os.path.join(target_dir, file)

                try:
                    # Check for subtitle tracks using mkvmerge
                    result = subprocess.run([
                        "mkvmerge", "--identify", file_path
                    ], capture_output=True, text=True, check=True)

                    subtitle_tracks = re.findall(r"Track ID (\d+): subtitles", result.stdout)

                    if subtitle_tracks:
                        # Remove subtitle tracks if present
                        subprocess.run([
                            "mkvmerge", "-o", new_file_path,
                            "--no-subtitles", file_path
                        ], check=True)
                    else:
                        # Move the file if no subtitles are found
                        os.rename(file_path, new_file_path)
                        print(f"No subtitles found, moved: {file_path} -> {new_file_path}")

                    # Extract audio tracks and write to the report if more than one audio track
                    audio_tracks = re.findall(r"Track ID (\d+): audio \((.*?)\)", result.stdout)
                    if len(audio_tracks) > 1:
                        report.write(f"{file}\n")
                        for track_id, language in audio_tracks:
                            report.write(f"  Track {track_id}: Language {language}\n")

                    # Delete the original file only if processed
                    if subtitle_tracks:
                        os.remove(file_path)
                        print(f"Cleaned and moved: {file_path} -> {new_file_path}")

                except subprocess.CalledProcessError as e:
                    print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    clean_movies("./movies_tagged", "./movies_cleaned")

