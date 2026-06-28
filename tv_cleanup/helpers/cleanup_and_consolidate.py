#!/usr/bin/env python3

import os
import shutil
import subprocess

def cleanup_and_consolidate():
    """Move tagged files back to main directory and clean up"""
    print("🧹 Cleaning up and consolidating files...")
    
    tagged_dir = "/storage/media/servarr/tvshows_tagged"
    main_dir = "/storage/media/servarr/tvshows"
    
    if not os.path.exists(tagged_dir):
        print("❌ Tagged directory not found")
        return
    
    # Move all shows from tagged back to main
    for show_folder in os.listdir(tagged_dir):
        show_path = os.path.join(tagged_dir, show_folder)
        if os.path.isdir(show_path):
            dest_path = os.path.join(main_dir, show_folder)
            
            print(f"📦 Moving {show_folder}...")
            
            # Remove destination if it exists
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            
            # Move the folder
            shutil.move(show_path, dest_path)
            print(f"✅ Moved {show_folder}")
    
    # Clean up empty directories
    cleanup_dirs = [
        "/storage/media/servarr/tvshows_tagged",
        "/storage/media/servarr/tvshows_organized", 
        "/storage/media/servarr/tvshows_failed"
    ]
    
    for dir_path in cleanup_dirs:
        if os.path.exists(dir_path):
            try:
                os.rmdir(dir_path)
                print(f"🗑️ Removed empty directory: {dir_path}")
            except OSError:
                print(f"⚠️ Could not remove {dir_path} (not empty)")
    
    print("\n✅ Cleanup complete!")
    print(f"📁 All files now in: {main_dir}")

if __name__ == "__main__":
    cleanup_and_consolidate() 