#!/bin/bash

for file in *.mkv; do
    # Remove all global tags
    echo "Removing tags from: $file"
    mkvpropedit "$file" --tags all:

    # Extract the season and episode number (e.g., S02E03)
    episode=$(echo "$file" | grep -oP 'S\d{2}E\d{2}')

    # Extract the episode title and replace underscores with spaces
    episode_name=$(echo "$file" | sed -E 's/.*S[0-9]{2}E[0-9]{2}_-_(.*)\.mkv/\1/' | tr '_' ' ')

    # Construct the correct title: "Tulsa King S02E03 - Oklahoma v. Manfredi"
    title="Tulsa King $episode - $episode_name"

    # Set the cleaned title tag
    echo "Setting title: $title for $file"
    mkvpropedit "$file" --edit info --set "title=$title"
done

echo "All MKV files processed successfully."

