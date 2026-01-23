#!/usr/bin/env python3

import os
import subprocess
import re

def check_mkv_file(mkv_file):
    """Check a single MKV file for tags and properties"""
    try:
        # Get mkvinfo output
        result = subprocess.run(['mkvinfo', mkv_file], capture_output=True, text=True)
        if result.returncode != 0:
            return f"❌ Error reading file: {result.stderr}"
        
        output = result.stdout
        
        # Check for tags
        has_tags = "Tags" in output
        has_title = "Title:" in output
        has_attachments = "Attachments" in output
        
        # Extract title if present
        title_match = re.search(r'Title: (.+)', output)
        title = title_match.group(1) if title_match else None
        
        # Check for any other properties that might be junk
        has_encoder_info = "Lavf" in output or "HandBrake" in output
        has_duration_tags = "DURATION" in output
        
        status = []
        if has_tags:
            status.append("❌ Has old tags")
        if has_attachments:
            status.append("❌ Has attachments")
        if has_encoder_info:
            status.append("⚠️  Has encoder info")
        if has_duration_tags:
            status.append("⚠️  Has duration tags")
        
        if title:
            status.append(f"✅ Title: {title}")
        else:
            status.append("❌ No title")
        
        return " | ".join(status) if status else "✅ Clean"
        
    except Exception as e:
        return f"❌ Error: {e}"

def verify_all_files():
    """Verify all MKV files in the tagged directory"""
    base_dir = "/storage/media/servarr/tvshows_tagged/Glee_(2009)"
    
    if not os.path.exists(base_dir):
        print(f"❌ Directory not found: {base_dir}")
        return
    
    print("🔍 Verifying MKV file cleanup and tagging...")
    print("=" * 80)
    
    total_files = 0
    clean_files = 0
    tagged_files = 0
    problematic_files = 0
    
    for season_folder in sorted(os.listdir(base_dir)):
        season_path = os.path.join(base_dir, season_folder)
        if not os.path.isdir(season_path) or not season_folder.startswith('Season_'):
            continue
        
        print(f"\n📁 {season_folder}:")
        
        for filename in sorted(os.listdir(season_path)):
            if not filename.endswith('.mkv'):
                continue
            
            total_files += 1
            mkv_file = os.path.join(season_path, filename)
            status = check_mkv_file(mkv_file)
            
            # Count statistics
            if "❌" in status:
                problematic_files += 1
            elif "✅ Clean" in status:
                clean_files += 1
            elif "✅ Title:" in status:
                tagged_files += 1
            
            print(f"  {filename}: {status}")
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY:")
    print(f"  Total files: {total_files}")
    print(f"  Clean files (no title): {clean_files}")
    print(f"  Properly tagged files: {tagged_files}")
    print(f"  Problematic files: {problematic_files}")
    
    if problematic_files == 0:
        print("\n✅ All files are properly cleaned and tagged!")
    else:
        print(f"\n⚠️  {problematic_files} files need attention")

if __name__ == "__main__":
    verify_all_files() 