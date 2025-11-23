#!/usr/bin/env python3

import os
import re

# Base directory to search
base_dir = "./"

# Categories
categories = {
    "100+ GB": {"count": 0, "size": 0, "formats": {"h265": {"count": 0, "size": 0}, "h264": {"count": 0, "size": 0}, "av1": {"count": 0, "size": 0}, "other": {"count": 0, "size": 0}}},
    "70-99 GB": {"count": 0, "size": 0, "formats": {"h265": {"count": 0, "size": 0}, "h264": {"count": 0, "size": 0}, "av1": {"count": 0, "size": 0}, "other": {"count": 0, "size": 0}}},
    "50-69 GB": {"count": 0, "size": 0, "formats": {"h265": {"count": 0, "size": 0}, "h264": {"count": 0, "size": 0}, "av1": {"count": 0, "size": 0}, "other": {"count": 0, "size": 0}}},
    "40-49 GB": {"count": 0, "size": 0, "formats": {"h265": {"count": 0, "size": 0}, "h264": {"count": 0, "size": 0}, "av1": {"count": 0, "size": 0}, "other": {"count": 0, "size": 0}}},
    "30-39 GB": {"count": 0, "size": 0, "formats": {"h265": {"count": 0, "size": 0}, "h264": {"count": 0, "size": 0}, "av1": {"count": 0, "size": 0}, "other": {"count": 0, "size": 0}}},
}

# Convert bytes to GB
def bytes_to_gb(size_in_bytes):
    return size_in_bytes / (1024 ** 3)

# Categorize file sizes
def categorize_file(size_gb):
    if size_gb >= 100:
        return "100+ GB"
    elif 70 <= size_gb < 100:
        return "70-99 GB"
    elif 50 <= size_gb < 70:
        return "50-69 GB"
    elif 40 <= size_gb < 50:
        return "40-49 GB"
    elif 30 <= size_gb < 40:
        return "30-39 GB"
    else:
        return None

# Determine file format from the name using regex
def determine_format(filename):
    filename_lower = filename.lower()
    if re.search(r"\bh265\b|\bhevc\b", filename_lower):
        return "h265"
    elif re.search(r"\bh264\b", filename_lower):
        return "h264"
    elif re.search(r"\bav1\b", filename_lower):
        return "av1"
    else:
        return "other"

# Walk through subdirectories
for root, _, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".mkv"):
            file_path = os.path.join(root, file)
            size_bytes = os.path.getsize(file_path)
            size_gb = bytes_to_gb(size_bytes)

            category = categorize_file(size_gb)
            if category:
                format_type = determine_format(file)
                categories[category]["count"] += 1
                categories[category]["size"] += size_gb
                categories[category]["formats"][format_type]["count"] += 1
                categories[category]["formats"][format_type]["size"] += size_gb

# Print results
print("Summary of MKV files by size categories (30GB+):")
for category, data in categories.items():
    print(f"\n{category}: {data['count']} files, {data['size']:.2f} GB total")
    for format_type, format_data in data["formats"].items():
        print(f"  {format_type}: {format_data['count']} files, {format_data['size']:.2f} GB")

