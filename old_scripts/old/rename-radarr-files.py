#!/usr/bin/python3

import os
import re

# Directory containing the files
directory = "./"  # Replace with your directory path if not the current directory

# Change to the target directory
os.chdir(directory)

# Regex pattern to match filenames
pattern = re.compile(r"(.+)\s\((\d{4})\)")

# Loop through all MKV files
for filename in os.listdir():
    if filename.endswith(".mkv"):
        match = pattern.match(filename)
        if match:
            # Extract title and year
            title = match.group(1).replace(" ", "_")  # Replace spaces with underscores
            year = match.group(2)
            new_filename = f"{title}_{year}.mkv"
            
            # Rename the file
            os.rename(filename, new_filename)
            print(f"Renamed: {filename} -> {new_filename}")
        else:
            print(f"Skipped: {filename} (does not match pattern)")

