#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import subprocess

def analyze_audio_tracks(source_dir):
    for file in os.listdir(source_dir):
        if file.endswith(".mkv"):
            file_path = os.path.join(source_dir, file)
            print(f"{file}")
            try:
                result = subprocess.run([
                    "mkvinfo", file_path], capture_output=True, text=True, check=True)

                lines = result.stdout.splitlines()
                current_track = None

                for line in lines:
                    line = line.strip()

                    # Detect start of a new track block
                    if line.startswith("+ Track"):
                        if current_track and current_track.get("type") == "audio":
                            print(f"  Track {current_track['track_number']}: Codec: {current_track['codec']}, Language: {current_track['language']}")
                        current_track = {"track_number": None, "codec": None, "language": "unknown", "type": None}

                    # Capture track details if inside a track block
                    if current_track is not None:
                        if "Track type:" in line:
                            current_track["type"] = line.split(":")[-1].strip()
                        if "Track number:" in line:
                            current_track["track_number"] = line.split(":")[-1].strip()
                        if "Codec ID:" in line:
                            current_track["codec"] = line.split(":")[-1].strip()
                        if "Language" in line:
                            current_track["language"] = line.split(":")[-1].strip()

                # Print the last track if it's audio
                if current_track and current_track.get("type") == "audio":
                    print(f"  Track {current_track['track_number']}: Codec: {current_track['codec']}, Language: {current_track['language']}")
                print()

            except subprocess.CalledProcessError as e:
                print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    analyze_audio_tracks("./")

