#!/usr/bin/env python3

import os
import re
import csv

# Config
WORKING_DIR = os.getcwd()  # Or set to your desired path, e.g. '/storage/media/servarr/tagged'
CSV_OUT = "imdb_scan_report.csv"  # Set to None if you don't want CSV output

IMDB_REGEX = re.compile(r"(tt\d{7,9})", re.IGNORECASE)

def find_imdbid_in_nfo(nfo_path):
    try:
        with open(nfo_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        match = IMDB_REGEX.search(content)
        return match.group(1) if match else None
    except Exception as e:
        return None

def scan_folders(base_path):
    results = []
    for root, dirs, files in os.walk(base_path):
        if 'movie.nfo' in files:
            nfo_path = os.path.join(root, 'movie.nfo')
            imdbid = find_imdbid_in_nfo(nfo_path)
            results.append({
                'folder': os.path.relpath(root, base_path),
                'nfo': True,
                'imdbid': imdbid or "NOT FOUND"
            })
        else:
            # Still log folders without NFO
            results.append({
                'folder': os.path.relpath(root, base_path),
                'nfo': False,
                'imdbid': "NO NFO"
            })
    return results

def print_report(results):
    print(f"{'Folder':60} | {'NFO?':5} | IMDb ID")
    print("-"*90)
    for r in results:
        print(f"{r['folder'][:60]:60} | {str(r['nfo']):5} | {r['imdbid']}")

def write_csv(results, path):
    with open(path, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["folder", "nfo", "imdbid"])
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"\n[INFO] CSV report written to {path}")

if __name__ == "__main__":
    print(f"[INFO] Scanning for movie.nfo files and IMDb IDs in: {WORKING_DIR}\n")
    results = scan_folders(WORKING_DIR)
    print_report(results)
    if CSV_OUT:
        write_csv(results, CSV_OUT)
