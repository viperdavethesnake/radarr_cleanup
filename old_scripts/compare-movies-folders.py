#!/usr/bin/env python3

import os
import sys

def list_folders(path):
    """List all folder names in the specified path."""
    try:
        return {folder for folder in os.listdir(path) if os.path.isdir(os.path.join(path, folder))}
    except FileNotFoundError:
        print(f"Error: Path '{path}' does not exist.")
        sys.exit(1)

def main():
    if len(sys.argv) != 3:
        print("Usage: ./folder_compare.py <main_path> <new_path>")
        sys.exit(1)

    # Read paths from command-line arguments
    main_path = sys.argv[1]
    new_path = sys.argv[2]

    # Get folder names in "main" and "new"
    main_folders = list_folders(main_path)
    new_folders = list_folders(new_path)

    # Find folders common to both
    common_folders = main_folders & new_folders

    # Print results
    print("Folders in both 'main' and 'new':")
    for folder in sorted(common_folders):
        print(f"  {folder}")

if __name__ == "__main__":
    main()

