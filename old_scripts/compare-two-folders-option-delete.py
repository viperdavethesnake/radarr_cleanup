#!/usr/bin/python3 

import os
import argparse

def get_file_info(folder_path):
    file_info = {}
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                file_info[file] = file_size
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    return file_info

def compare_folders(source_folder, target_folder, delete_copied):
    source_files = get_file_info(source_folder)
    target_files = get_file_info(target_folder)

    copied_files = [file for file, size in source_files.items()
                    if file in target_files and target_files[file] == size]

    print(f"Files already copied ({len(copied_files)}):")
    for file in copied_files:
        print(file)
        if delete_copied:
            try:
                os.remove(os.path.join(source_folder, file))
                print(f"Deleted: {file}")
            except Exception as e:
                print(f"Error deleting {file}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Compare folders and optionally delete copied files.")
    parser.add_argument('source_folder', help="Path to the source folder")
    parser.add_argument('target_folder', help="Path to the target folder")
    parser.add_argument('--delete', action='store_true', help="Delete copied files from the source folder")

    args = parser.parse_args()
    compare_folders(args.source_folder, args.target_folder, args.delete)

if __name__ == "__main__":
    main()

