#!/usr/bin/env python3

import os
import argparse
import shutil
from typing import List


def list_immediate_subdirs(path: str) -> List[str]:
    try:
        return [
            os.path.join(path, name)
            for name in os.listdir(path)
            if os.path.isdir(os.path.join(path, name))
        ]
    except FileNotFoundError:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="List movies that are COMPLETED in cleaned (i.e., not present in tagged). Optionally move them."
    )
    parser.add_argument(
        "--tagged",
        default="./tagged",
        help="Tagged source directory (default: ./tagged)",
    )
    parser.add_argument(
        "--cleaned",
        default="./cleaned",
        help="Cleaned destination directory (default: ./cleaned)",
    )
    parser.add_argument(
        "--dest",
        default="/storage/media/movies",
        help="Destination path to move completed items when --move is set (default: /storage/media/movies)",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="If set, move completed items to --dest",
    )
    args = parser.parse_args()

    tagged_root = os.path.abspath(args.tagged)
    cleaned_root = os.path.abspath(args.cleaned)
    dest_root = os.path.abspath(args.dest)

    cleaned_folders = list_immediate_subdirs(cleaned_root)
    completed = []

    for cleaned_folder in sorted(cleaned_folders, key=lambda p: os.path.basename(p).lower()):
        base = os.path.basename(cleaned_folder.rstrip(os.sep))
        tagged_folder = os.path.join(tagged_root, base)

        # Completed per requested logic: exists in cleaned, NOT in tagged
        if not os.path.isdir(tagged_folder):
            completed.append((base, cleaned_folder))

    print(f"Scanned cleaned folders: {len(cleaned_folders)}")
    print(f"Completed: {len(completed)}")
    if completed:
        print("\nCompleted list:")
        for base, _ in completed:
            print(f"- {base}")

    if args.move and completed:
        os.makedirs(dest_root, exist_ok=True)
        print(f"\nMoving {len(completed)} completed items to: {dest_root}")
        for base, cleaned_folder in completed:
            dst_path = os.path.join(dest_root, base)
            if os.path.exists(dst_path):
                print(f"- {base}: skipped (already exists at destination)")
                continue
            try:
                shutil.move(cleaned_folder, dst_path)
                print(f"- {base}: moved")
            except Exception as e:
                print(f"- {base}: move failed ({e})")


if __name__ == "__main__":
    main()


