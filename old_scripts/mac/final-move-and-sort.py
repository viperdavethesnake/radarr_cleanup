#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import subprocess
import re

def set_language_tags(source_dir, review_dir, target_dir):
    os.makedirs(review_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    for file in os.listdir(source_dir):
        if file.endswith(".mkv"):
            file_path = os.path.join(source_dir, file)

            try:
                # Check the number of audio tracks
                result = subprocess.run([
                    "mkvmerge", "--identify", file_path
                ], capture_output=True, text=True, check=True)

                audio_tracks = re.findall(r"Track ID (\d+): audio", result.stdout)

                if len(audio_tracks) > 1:
                    # Move file with multiple audio tracks to review folder
                    review_path = os.path.join(review_dir, file)
                    os.rename(file_path, review_path)
                    print(f"Moved to review: {file_path} -> {review_path}")
                else:
                    # Set language tags for video and audio if there's only one audio track
                    subprocess.run([
                        "mkvpropedit", file_path, "--edit", "track:1", "--set", "language=eng"
                    ], check=True)

                    subprocess.run([
                        "mkvpropedit", file_path, "--edit", "track:2", "--set", "language=eng"
                    ], check=True)

                    # Move the processed file to the target directory
                    target_path = os.path.join(target_dir, file)
                    os.rename(file_path, target_path)
                    print(f"Language tags set and moved: {file_path} -> {target_path}")

            except subprocess.CalledProcessError as e:
                print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    set_language_tags("./movies_cleaned", "./movies_review", "./movies_final")

