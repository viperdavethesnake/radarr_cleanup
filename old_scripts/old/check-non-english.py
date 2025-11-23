#!/usr/bin/python3

import os
import subprocess

def find_non_english_mkv_files(directory):
    """
    Scan a directory for MKV files with non-English video or audio language tags.

    :param directory: Path to the directory containing MKV files.
    """
    non_english_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".mkv"):
                file_path = os.path.join(root, file)
                try:
                    # Run mkvmerge to inspect the file metadata
                    result = subprocess.run(
                        ["mkvmerge", "-i", file_path],
                        text=True,
                        capture_output=True,
                        check=True
                    )
                    output = result.stdout

                    # Check for language tags not set to English
                    if "language:eng" not in output.lower():
                        non_english_files.append(file_path)
                except subprocess.CalledProcessError as e:
                    print(f"Error processing {file_path}: {e}")

    return non_english_files


if __name__ == "__main__":
    directory = input("Enter the directory to scan for MKV files: ").strip()
    if not os.path.isdir(directory):
        print("Invalid directory path. Please provide a valid path.")
        exit(1)

    print("Scanning for MKV files with non-English language tags...")
    non_english_files = find_non_english_mkv_files(directory)

    if non_english_files:
        print("\nMKV files with non-English language tags:")
        for file in non_english_files:
            print(file)
    else:
        print("All MKV files have English language tags for video and audio.")

