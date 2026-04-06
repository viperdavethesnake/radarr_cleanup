#!/bin/bash
# Wrapper script to run benchmark with proper environment

# Resolve repo-relative defaults (override with RC_* env vars)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FFMPEG_PREFIX="${RC_FFMPEG_PREFIX:-$REPO_ROOT/ffmpeg-build}"
VMAF_LIB_DIR="${RC_VMAF_LIB_DIR:-$REPO_ROOT/vmaf-install/lib/x86_64-linux-gnu}"

# Set library paths for custom FFmpeg with VMAF
export LD_LIBRARY_PATH="$FFMPEG_PREFIX/lib:$VMAF_LIB_DIR:$LD_LIBRARY_PATH"

# Add custom FFmpeg to PATH
export PATH="$FFMPEG_PREFIX/bin:$PATH"

# Run the benchmark with arguments
python3 nvidia_av1_benchmark.py "$@"
