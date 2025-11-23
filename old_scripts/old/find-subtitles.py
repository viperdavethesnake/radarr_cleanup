#!/usr/bin/python3

import os
import subprocess

def find_mkv_with_subtitles(directory):
    """
    Scan a directory for MKV files with subtitle tracks.

    :param directory: Path to the directory containing MKV files.
    :return: List of MKV files with subtitle tracks.
    """
    files_with_subtitles = []

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

                    # Check for subtitle tracks in the output
                    if "subtitles" in output.lower():
                        files_with_subtitles.append(file_path)
                except subprocess.CalledProcessError as e:
                    print(f"Error processing {file_path}: {e}")

    return files_with_subtitles

if __name__ == "__main__":
    directory = input("Enter the directory to scan for MKV files: ").strip()
    if not os.path.isdir(directory):
        print("Invalid directory path. Please provide a valid path.")
        exit(1)

    print("Scanning for MKV files with subtitles...")
    files_with_subtitles = find_mkv_with_subtitles(directory)

    if files_with_subtitles:
        print("\nMKV files with subtitles:")
        for file in files_with_subtitles:
            print(file)
    else:
        print("No MKV files with subtitles found.")

