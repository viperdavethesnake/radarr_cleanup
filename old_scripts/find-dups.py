#!/usr/bin/python3
import os
import re
from collections import defaultdict

# Source directory
SOURCE_DIR = "./"

# Regex pattern to extract the movie title and year
# Example: Movie_Title_(Year)-xxx
MOVIE_PATTERN = re.compile(r"^(.*)_(\(\d{4}\))")

def extract_movie_info(filename):
    """
    Extract movie title and year from a filename.
    Returns a tuple of (title, year) or None if not matching.
    """
    match = MOVIE_PATTERN.match(filename)
    if match:
        title = match.group(1).replace("_", " ")
        year = match.group(2)
        return title, year
    return None

def find_duplicates(directory):
    """
    Find and group files with the same movie title and year.
    """
    movie_groups = defaultdict(list)

    # Iterate over files in the directory
    for file in os.listdir(directory):
        # Skip non-MKV files
        if not file.endswith(".mkv"):
            continue
        
        # Extract movie info
        movie_info = extract_movie_info(file)
        if movie_info:
            movie_groups[movie_info].append(file)
    
    # Filter out groups with only one file
    duplicates = {key: value for key, value in movie_groups.items() if len(value) > 1}
    return duplicates

def main():
    # Find duplicates
    duplicates = find_duplicates(SOURCE_DIR)

    if duplicates:
        print("\n[INFO] Duplicate Movie Titles and Years Found:\n")
        for (title, year), files in duplicates.items():
            print(f"{title} {year}:")
            for file in files:
                print(f"  - {file}")
    else:
        print("\n[INFO] No duplicate movie titles and years found.")

if __name__ == "__main__":
    main()

