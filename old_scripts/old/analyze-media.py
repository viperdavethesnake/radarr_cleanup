#!/usr/bin/env python3

import subprocess
import json
import sys


def analyze_media(file_path):
    """
    Analyze the video, audio, and subtitle streams of a media file.

    Args:
        file_path (str): Path to the media file.

    Returns:
        dict: A dictionary containing details of video, audio, and subtitle streams.
    """
    streams = {"video": [], "audio": [], "subtitles": []}

    try:
        # Run ffprobe to get stream details
        cmd = [
            "ffprobe", "-v", "error",
            "-show_streams", "-select_streams", "v",  # Video streams
            "-show_entries",
            "stream=index,codec_name,codec_type,profile,width,height,r_frame_rate,avg_frame_rate,bit_rate,duration",
            "-of", "json", file_path
        ]
        video_info = subprocess.check_output(cmd, text=True)
        streams["video"] = json.loads(video_info).get("streams", [])

        cmd = [
            "ffprobe", "-v", "error",
            "-show_streams", "-select_streams", "a",  # Audio streams
            "-show_entries",
            "stream=index,codec_name,codec_type,channels,channel_layout,sample_rate,bit_rate,duration,disposition,language",
            "-of", "json", file_path
        ]
        audio_info = subprocess.check_output(cmd, text=True)
        streams["audio"] = json.loads(audio_info).get("streams", [])

        cmd = [
            "ffprobe", "-v", "error",
            "-show_streams", "-select_streams", "s",  # Subtitle streams
            "-show_entries",
            "stream=index,codec_name,codec_type,disposition,language",
            "-of", "json", file_path
        ]
        subtitle_info = subprocess.check_output(cmd, text=True)
        streams["subtitles"] = json.loads(subtitle_info).get("streams", [])

    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON output: {e}", file=sys.stderr)

    return streams


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <media_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    streams = analyze_media(file_path)

    print("Video Streams:")
    for video in streams["video"]:
        print(json.dumps(video, indent=4))

    print("\nAudio Streams:")
    for audio in streams["audio"]:
        print(json.dumps(audio, indent=4))

    print("\nSubtitle Streams:")
    for subtitle in streams["subtitles"]:
        print(json.dumps(subtitle, indent=4))


if __name__ == "__main__":
    main()

