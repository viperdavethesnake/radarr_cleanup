#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import re
import subprocess

def tag_movies(source_dir, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    for file in os.listdir(source_dir):
        if file.endswith(".mkv"):
            file_path = os.path.join(source_dir, file)
            match = re.match(r'(.+?)_(\d{4})_\[imdbid-tt\d+\]\.mkv', file)
            if match:
                title = match.group(1).replace('_', ' ')
                year = match.group(2)
                formatted_title = f"{title} ({year})"

                try:
                    # Step 1: Remove all tags using the correct syntax
                    subprocess.run(["mkvpropedit", file_path, "--tags", "global:"], check=True)

                    # Step 2: Apply the MKV tag using mkvpropedit
                    subprocess.run([
                        "mkvpropedit", file_path,
                        "--set", f"title={formatted_title}"
                    ], check=True)
                    print(f"Tagged: {file_path} with title '{formatted_title}'")

                    # Move the tagged file to the target directory
                    new_file_path = os.path.join(target_dir, file)
                    os.rename(file_path, new_file_path)
                except subprocess.CalledProcessError as e:
                    print(f"Error processing {file_path}: {e}")
            else:
                print(f"Filename format not recognized: {file}")

if __name__ == "__main__":
    tag_movies("./movies_renamed", "./movies_tagged")

