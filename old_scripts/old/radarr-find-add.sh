#!/bin/bash

# Load .env file
if [ -f .env ]; then
    source .env
elif [ -f ../../.env ]; then
    source ../../.env
fi

RADARR_API_KEY="${RADARR_API_KEY:-your_api_key_here}"
RADARR_URL="${RADARR_URL:-http://192.168.36.123:7878}"
RADARR_ROOT_FOLDER="/Volumes/More Space/servarr/media/movies"
QUALITY_PROFILE_ID=7  # Confirmed ID for "Mine"
MOVIE_LIST="/storage/media/working/movies_working/1080p_not_h264_h265.txt"

# Process the movie list and add them to Radarr
while IFS= read -r line; do
    # Extract the movie title using pattern matching
    movie=$(echo "$line" | sed -E 's/([^-]+)_\([0-9]{4}\).*/\1/' | tr '_' ' ')
    echo "Searching for '$movie' in Radarr..."

    # Search Radarr for the movie
    movie_data=$(curl -s --request GET \
      --url "$RADARR_URL/api/v3/movie/lookup?term=$(echo $movie | sed 's/ /%20/g')" \
      --header "X-Api-Key: $RADARR_API_KEY" | jq '.[0]')

    # Extract TMDB ID
    movie_id=$(echo "$movie_data" | jq '.tmdbId')
    
    if [ "$movie_id" != "null" ]; then
        echo "Adding '$movie' to Radarr with Quality Profile 'Mine'..."
        curl -s --request POST \
          --url "$RADARR_URL/api/v3/movie" \
          --header "Content-Type: application/json" \
          --header "X-Api-Key: $RADARR_API_KEY" \
          --data "{
            \"title\": $(echo "$movie_data" | jq '.title'),
            \"tmdbId\": $movie_id,
            \"qualityProfileId\": $QUALITY_PROFILE_ID,
            \"monitored\": true,
            \"rootFolderPath\": \"$RADARR_ROOT_FOLDER\",
            \"addOptions\": {
                \"searchForMovie\": true
            }
          }"
        echo "'$movie' added successfully!"
    else
        echo "Movie not found in Radarr: '$movie'"
    fi
done < "$MOVIE_LIST"

