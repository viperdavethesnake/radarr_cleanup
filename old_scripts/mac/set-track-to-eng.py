#!/usr/bin/python3

import os
import subprocess

def set_language_to_english(directory):
    """
    Set the language tag to English for track 1 (video) and track 2 (audio) in all MKV files in the specified directory.

    :param directory: Path to the directory containing MKV files.
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".mkv"):
                file_path = os.path.join(root, file)
                try:
                    print(f"Processing: {file_path}")

                    # Set language to English for track 1 (video)
                    subprocess.run(
                        ["mkvpropedit", file_path, "--edit", "track:1", "--set", "language=eng"],
                        text=True,
                        capture_output=True,
                        check=True
                    )

                    # Set language to English for track 2 (audio)
                    subprocess.run(
                        ["mkvpropedit", file_path, "--edit", "track:2", "--set", "language=eng"],
                        text=True,
                        capture_output=True,
                        check=True
                    )

                    print(f"Successfully set language to English for: {file_path}")
                except subprocess.CalledProcessError as e:
                    print(f"Error processing {file_path}: {e.stderr.strip()}")

if __name__ == "__main__":
    directory = input("Enter the directory to process MKV files: ").strip()
    if not os.path.isdir(directory):
        print("Invalid directory path. Please provide a valid path.")
        exit(1)

    print("Setting language tags to English for MKV tracks...")
    set_language_to_english(directory)
    print("Done.")

