#!/usr/bin/python3

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

def remove_subtitles(file_path):
    """
    Removes subtitles from an MKV file and replaces the original file.

    Args:
        file_path (str): Path to the MKV file.
    """
    print(f"Checking: {file_path}")
    try:
        # Check if the file has subtitles
        result = subprocess.run(["mkvmerge", "--identify", file_path], capture_output=True, text=True)
        if "subtitles" in result.stdout.lower():
            print(f"Subtitles found in {file_path}")
            # Create a temporary output file
            output_file = f"{file_path}.tmp"
            # Remove subtitles and save to the new file
            command = ["mkvmerge", "-o", output_file, "--no-subtitles", file_path]
            subprocess.run(command, check=True)
            # Replace the original file
            os.replace(output_file, file_path)
            print(f"Processed and replaced: {file_path}")
        else:
            print(f"No subtitles found in {file_path}. Skipping.")
    except subprocess.CalledProcessError as e:
        print(f"Error processing {file_path}: {e}")

def process_mkv_files(directory):
    """
    Process all MKV files in a directory to remove subtitles in parallel.

    Args:
        directory (str): Path to the directory containing MKV files.
    """
    mkv_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".mkv")]
    with ThreadPoolExecutor() as executor:
        executor.map(remove_subtitles, mkv_files)

if __name__ == "__main__":
    directory = input("Enter the directory containing MKV files: ").strip()
    if not os.path.isdir(directory):
        print(f"Invalid directory: {directory}")
    else:
        process_mkv_files(directory)


