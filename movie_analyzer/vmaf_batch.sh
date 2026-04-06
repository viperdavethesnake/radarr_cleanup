#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FFMPEG_PREFIX="${RC_FFMPEG_PREFIX:-$REPO_ROOT/ffmpeg-build}"
VMAF_LIB_DIR="${RC_VMAF_LIB_DIR:-$REPO_ROOT/vmaf-install/lib/x86_64-linux-gnu}"
FFMPEG_BIN="${RC_FFMPEG_BIN:-$FFMPEG_PREFIX/bin/ffmpeg}"
WORK_DIR="${RC_WORK_DIR:-/space/media/working}"

export LD_LIBRARY_PATH="$FFMPEG_PREFIX/lib:$VMAF_LIB_DIR:$LD_LIBRARY_PATH"
mkdir -p "$WORK_DIR/encoded"

echo "=== COMPLETE VMAF ANALYSIS ==="
echo "Scene | CQ24 VMAF | CQ26 VMAF | CQ28 VMAF | Compression Winner"
echo "------|-----------|-----------|-----------|-------------------"

# Test all combinations
for scene in high_motion low_motion complex; do
    echo -n "${scene} | "
    
    for cq in 24 26 28; do
        source="samples/extracts/The_King's_Speech_(2010)-[imdbid-tt1504320]-[1080p]-[h264]-[DTS]_${scene}.mkv"
        encoded="$WORK_DIR/encoded/The_King's_Speech_(2010)-[imdbid-tt1504320]-[1080p]-[h264]-[DTS]_${scene}_pp5_cq${cq}.mkv"
        
        if [[ -f "$source" && -f "$encoded" ]]; then
            vmaf_score=$("$FFMPEG_BIN" -i "$source" -i "$encoded" -lavfi "[0:v][1:v]libvmaf=log_fmt=json:log_path=vmaf_${scene}_cq${cq}.json:n_threads=4" -f null - 2>&1 | grep "VMAF score:" | tail -1 | sed 's/.*VMAF score: //' | sed 's/rate.*//')
            echo -n "${vmaf_score} | "
        else
            echo -n "missing | "
        fi
    done
    
    echo "CQ28 (best compression)"
done

echo ""
echo "📊 VMAF Results Summary:"
echo "• VMAF ≥95: Excellent (visually transparent)"  
echo "• VMAF 90-95: Very good quality"
echo "• VMAF 85-90: Good quality"
echo "• VMAF <85: May have visible artifacts"
