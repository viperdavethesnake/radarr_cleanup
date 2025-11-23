#!/usr/bin/python3

import os

# List of Apple-specific hidden files to remove
APPLE_HIDDEN_FILES = [".DS_Store", ".AppleDouble", "._"]

def remove_hidden_files(target_directory):
    """Remove Apple-specific hidden files from a directory and its subdirectories."""
    for root, dirs, files in os.walk(target_directory):
        for file in files:
            if any(file.startswith(prefix) for prefix in APPLE_HIDDEN_FILES):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
                except Exception as e:
                    print(f"Failed to remove {file_path}: {e}")


if __name__ == "__main__":
    target_directory = input("Enter the directory to clean: ").strip()
    if os.path.exists(target_directory) and os.path.isdir(target_directory):
        print(f"Starting cleanup in: {target_directory}")
        remove_hidden_files(target_directory)
        print("Cleanup complete.")
    else:
        print("Invalid directory. Please enter a valid path.")

