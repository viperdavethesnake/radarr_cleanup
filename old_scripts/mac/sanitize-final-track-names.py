#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import subprocess

def clear_track_names(source_dir):
    """Clears all 'Name' fields from all tracks in MKV files using mkvpropedit."""
    for file in os.listdir(source_dir):
        if file.endswith(".mkv"):
            file_path = os.path.join(source_dir, file)
            print(f"Processing: {file}")
            try:
                # Use mkvpropedit to clear the 'Name' field for all tracks
                subprocess.run(
                    ["mkvpropedit", file_path, "--edit", "track:a1", "--delete", "name"],
                    capture_output=True, text=True, check=True
                )
                subprocess.run(
                    ["mkvpropedit", file_path, "--edit", "track:a2", "--delete", "name"],
                    capture_output=True, text=True
                )
                subprocess.run(
                    ["mkvpropedit", file_path, "--edit", "track:a3", "--delete", "name"],
                    capture_output=True, text=True
                )
                subprocess.run(
                    ["mkvpropedit", file_path, "--edit", "track:a4", "--delete", "name"],
                    capture_output=True, text=True
                )
                subprocess.run(
                    ["mkvpropedit", file_path, "--edit", "track:v1", "--delete", "name"],
                    capture_output=True, text=True
                )
                print(f"✔ Cleared 'Name' fields for all tracks in: {file}\n")

            except subprocess.CalledProcessError as e:
                print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    clear_track_names("./")

