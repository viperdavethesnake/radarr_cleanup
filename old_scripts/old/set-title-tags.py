#!/usr/bin/python3

import os
import re
import subprocess

# Ask the user for the directory containing the files
directory = input("Enter the path to the directory containing your files: ").strip()

# Change to the directory
try:
    os.chdir(directory)
except FileNotFoundError:
    print(f"Error: Directory '{directory}' not found.")
    exit()

# Regex pattern to extract title and year from filenames
pattern = re.compile(r"(.+)_([0-9]{4})\.mkv")

# Loop through files in the directory
for filename in os.listdir():
    match = pattern.match(filename)
    if match and filename.endswith(".mkv"):
        # Extract title and year from filename
        title = match.group(1).replace("_", " ")
        year = match.group(2)
        full_title = f"{title} ({year})"

        try:
            # Remove all existing tags
            subprocess.run(["mkvpropedit", filename, "--tags", "global:"], check=True)
            # Set the title tag
            subprocess.run(["mkvpropedit", filename, "--set", f"title={full_title}"], check=True)
            print(f"Processed: {filename} -> Title set to '{full_title}'")
        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")
    else:
        print(f"Skipped: {filename} (does not match pattern)")

