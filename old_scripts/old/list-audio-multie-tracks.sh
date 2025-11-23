#!/bin/bash

# Directory containing the MKV files
DIRECTORY="./"  # Replace with your directory path if not the current directory

# Loop through all MKV files in the directory
for FILE in "$DIRECTORY"/*.mkv; do
    # Extract audio track details using mkvinfo
    AUDIO_TRACKS=$(mkvinfo "$FILE" | grep -A 2 "Track type: audio")
    
    # Count the number of audio tracks
    AUDIO_COUNT=$(echo "$AUDIO_TRACKS" | grep "Track type: audio" | wc -l)
    
    if [ "$AUDIO_COUNT" -gt 1 ]; then
        echo "File: $(basename "$FILE")"
        echo "  Number of audio tracks: $AUDIO_COUNT"
        
        # Extract and display the language tags
        echo "$AUDIO_TRACKS" | grep -E "Track type: audio|Language:" | sed 's/^/  /'
        echo
    fi
done

