#!/usr/bin/env python3

import os
import random

def pick_folders(base_dir, n=5):
    folders = [f for f in sorted(os.listdir(base_dir))
               if os.path.isdir(os.path.join(base_dir, f))
               and os.path.exists(os.path.join(base_dir, f, "tags.xml"))]
    if not folders:
        print("No folders with tags.xml found!")
        return []
    if len(folders) <= n:
        return folders
    return random.sample(folders, n)

def show_tags(base_dir, n=5):
    folders = pick_folders(base_dir, n)
    if not folders:
        return
    for folder in folders:
        tags_path = os.path.join(base_dir, folder, "tags.xml")
        print("\n" + "="*70)
        print(f"TAGS FOR: {folder}")
        print("="*70)
        try:
            with open(tags_path, "r", encoding="utf-8") as f:
                print(f.read())
        except Exception as e:
            print(f"❌ Could not read {tags_path}: {e}")

if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    show_tags(base, n)

