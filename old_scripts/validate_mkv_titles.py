#!/usr/bin/python3
import subprocess
import re
import os

# Source directory
SOURCE_DIR = "./"

# Regular expression to check title format "Movie Title (Year)"
TITLE_FORMAT_PATTERN = re.compile(r"^(.*)\s\(\d{4}\)$")

def extract_title_from_mkv(file):
    """
    Extract the title from an MKV file using mkvinfo.
    Returns the title if found, otherwise None.
    """
    try:
        # Run mkvinfo command to extract metadata
        result = subprocess.run(["mkvinfo", file], capture_output=True, text=True, check=True)
        output = result.stdout.splitlines()

        title = None
        for line in output:
            if "| + Title:" in line:
                title = line.split(":")[-1].strip()
                break

        return title
    except subprocess.CalledProcessError as e:
        print(f"Error processing {file}: {e}")
        return None

def validate_titles(directory):
    """
    Validate MKV files to ensure that the title is set and formatted correctly.
    Returns a tuple with two lists:
    - Missing title list
    - Incorrectly formatted title list
    """
    missing_title = []
    incorrect_format = []

    # Iterate over files in the directory
    for file in os.listdir(directory):
        # Skip non-MKV files
        if not file.endswith(".mkv"):
            continue
        
        # Extract title
        title = extract_title_from_mkv(os.path.join(directory, file))
        
        if title is None:
            missing_title.append(file)
        elif not TITLE_FORMAT_PATTERN.match(title):
            incorrect_format.append(file)
    
    return missing_title, incorrect_format

def main():
    # Validate movie titles
    missing_title, incorrect_format = validate_titles(SOURCE_DIR)

    # Print results
    if missing_title:
        print("\n[INFO] Movies missing the Title field:\n")
        for file in missing_title:
            print(f"  - {file}")
    
    if incorrect_format:
        print("\n[INFO] Movies with incorrect title format:\n")
        for file in incorrect_format:
            print(f"  - {file}")

if __name__ == "__main__":
    main()

