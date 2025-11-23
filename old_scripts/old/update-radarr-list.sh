#!/bin/bash

# Load .env file
if [ -f .env ]; then
    source .env
elif [ -f ../../.env ]; then
    source ../../.env
fi

RADARR_API_KEY="${RADARR_API_KEY:-your_api_key_here}"
RADARR_URL="${RADARR_URL:-http://192.168.36.123:7878}"

while IFS= read -r movie; do
    echo "Adding $movie to Radarr..."
    movie_data=$(curl -s --request GET \
      --url "$RADARR_URL/api/v3/movie/lookup?term=$(echo $movie | sed 's/ /%20/g')" \
      --header "X-Api-Key: $RADARR_API_KEY" | jq '.[0]')

    movie_id=$(echo "$movie_data" | jq '.tmdbId')
    if [ "$movie_id" != "null" ]; then
        curl -s --request POST \
          --url "$RADARR_URL/api/v3/movie" \
          --header "Content-Type: application/json" \
          --header "X-Api-Key: $RADARR_API_KEY" \
          --data "{
            \"title\": $(echo "$movie_data" | jq '.title'),
            \"tmdbId\": $movie_id,
            \"qualityProfileId\": 1,
            \"monitored\": true,
            \"rootFolderPath\": \"/storage/media/movies\",
            \"addOptions\": {
                \"searchForMovie\": true
            }
          }"
        echo "$movie added successfully!"
    else
        echo "Movie not found in Radarr: $movie"
    fi
done < <(find /storage/media/movies -type f -name "*2160p*h264*" -print | sed -E 's#.*/([^/]+)_\([0-9]{4}\)/.*#\1#' | sort | uniq)

