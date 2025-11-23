#!/bin/bash
# Wrapper script to run benchmark with proper environment

# Set library paths for custom FFmpeg with VMAF
export LD_LIBRARY_PATH="/home/david/git/radarr_cleanup/ffmpeg-build/lib:/home/david/git/radarr_cleanup/vmaf-install/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# Add custom FFmpeg to PATH
export PATH="/home/david/git/radarr_cleanup/ffmpeg-build/bin:$PATH"

# Run the benchmark with arguments
python3 nvidia_av1_benchmark.py "$@"
