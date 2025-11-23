#!/bin/bash
export LD_LIBRARY_PATH="/home/david/git/radarr_cleanup/ffmpeg-build/lib:/home/david/git/radarr_cleanup/vmaf-install/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

echo "=== SVT-AV1 vs NVENC AV1 COMPARISON TEST ==="
echo "Testing same x264 samples with software SVT-AV1..."
echo ""

# Test parameters based on your suggestion
CRF_VALUES="22 24 26"
PRESET="4"

echo "Settings: CRF 22/24/26, Preset 4 (balanced speed/quality)"
echo ""

for scene in high_motion low_motion complex; do
    source="samples/extracts/The_King's_Speech_(2010)-[imdbid-tt1504320]-[1080p]-[h264]-[DTS]_${scene}.mkv"
    
    if [[ ! -f "$source" ]]; then
        echo "⚠️  Source missing: $source"
        continue
    fi
    
    echo "🎬 Testing: $scene"
    source_size=$(stat -f%z "$source" 2>/dev/null || stat -c%s "$source")
    source_mb=$((source_size / 1024 / 1024))
    
    for crf in $CRF_VALUES; do
        output="/space/media/working/encoded/svt_av1_${scene}_crf${crf}.mkv"
        
        echo -n "  CRF${crf}: "
        start_time=$(date +%s.%N)
        
        /home/david/git/radarr_cleanup/ffmpeg-build/bin/ffmpeg -y -i "$source" \
            -c:v libsvtav1 -crf $crf -preset $PRESET \
            -c:a copy -c:s copy \
            "$output" &>/dev/null
        
        end_time=$(date +%s.%N)
        encode_time=$(echo "$end_time - $start_time" | bc -l)
        
        if [[ -f "$output" ]]; then
            output_size=$(stat -f%z "$output" 2>/dev/null || stat -c%s "$output")
            output_mb=$((output_size / 1024 / 1024))
            compression=$(echo "scale=1; $source_mb / $output_mb" | bc -l)
            
            # Quick VMAF test
            vmaf_score=$(/home/david/git/radarr_cleanup/ffmpeg-build/bin/ffmpeg -i "$source" -i "$output" -lavfi "[0:v][1:v]libvmaf=n_threads=4" -f null - 2>&1 | grep "VMAF score:" | tail -1 | sed 's/.*VMAF score: //' | sed 's/rate.*//')
            
            printf "%dMB→%dMB (%sx), %.1fs, VMAF %.1f\n" $source_mb $output_mb $compression $encode_time $vmaf_score
        else
            echo "FAILED"
        fi
    done
    echo ""
done

echo "🆚 COMPARISON SUMMARY:"
echo "Hardware NVENC CQ28: ~1.5x compression, 78-94 VMAF, ~5 seconds"
echo "Software SVT-AV1:    [Results above]"
