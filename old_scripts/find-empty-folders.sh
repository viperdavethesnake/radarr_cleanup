#!/usr/bin/env bash

base_dir="./" # Replace with your target directory

# Loop through all subdirectories of the base directory
find "$base_dir" -mindepth 1 -maxdepth 1 -type d | while read -r dir; do
  # Check if the directory has any *.mkv files (one level only)
  if ! find "$dir" -maxdepth 1 -type f -name "*.mkv" | grep -q .; then
    echo "$dir"
  fi
done

