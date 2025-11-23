#!/usr/bin/env python3

import os
import argparse
from typing import List, Optional, Tuple


def list_immediate_subdirs(path: str) -> List[str]:
    try:
        return [
            os.path.join(path, name)
            for name in os.listdir(path)
            if os.path.isdir(os.path.join(path, name))
        ]
    except FileNotFoundError:
        return []


def find_mkvs(folder: str) -> List[str]:
    try:
        return [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".mkv") and os.path.isfile(os.path.join(folder, f))
        ]
    except FileNotFoundError:
        return []


def pick_largest(paths: List[str]) -> Optional[str]:
    if not paths:
        return None
    return max(paths, key=lambda p: os.path.getsize(p))


def has_extras(folder: str) -> Tuple[bool, List[str]]:
    required = ["movie.nfo", "poster.jpg"]
    missing = [f for f in required if not os.path.isfile(os.path.join(folder, f))]
    return (len(missing) == 0, missing)


def main():
    parser = argparse.ArgumentParser(
        description="Identify movies incorrectly moved to 'movies' while still incomplete."
    )
    parser.add_argument(
        "--movies",
        default="/storage/media/movies",
        help="Destination movies directory (default: /storage/media/movies)",
    )
    parser.add_argument(
        "--tagged",
        default="/storage/media/tagged",
        help="Tagged source directory (default: /storage/media/tagged)",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.50,
        help="Min acceptable dest_size/source_size ratio (default: 0.50)",
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=1.30,
        help="Max acceptable dest_size/source_size ratio (default: 1.30)",
    )
    args = parser.parse_args()

    movies_root = os.path.abspath(args.movies)
    tagged_root = os.path.abspath(args.tagged)

    movie_folders = list_immediate_subdirs(movies_root)

    mis_moved = []

    for dest_folder in sorted(movie_folders, key=lambda p: os.path.basename(p).lower()):
        base = os.path.basename(dest_folder.rstrip(os.sep))
        tagged_folder = os.path.join(tagged_root, base)

        reasons: List[str] = []

        # Core condition: If a folder exists in tagged, it wasn't "completed" per your rule.
        if os.path.isdir(tagged_folder):
            reasons.append("tagged counterpart still exists")

        # Extras check in the destination
        extras_ok, missing = has_extras(dest_folder)
        if not extras_ok:
            reasons.append("missing extras: " + ",".join(missing))

        # Size ratio check between destination and tagged largest MKVs
        dest_mkvs = find_mkvs(dest_folder)
        src_mkvs = find_mkvs(tagged_folder) if os.path.isdir(tagged_folder) else []
        if dest_mkvs and src_mkvs:
            dest_main = pick_largest(dest_mkvs)
            src_main = pick_largest(src_mkvs)
            if dest_main and src_main:
                try:
                    dest_size = os.path.getsize(dest_main)
                    src_size = os.path.getsize(src_main)
                    if src_size > 0:
                        ratio = dest_size / src_size
                        if ratio < args.min_ratio:
                            reasons.append(f"size ratio too small ({ratio:.2f} < {args.min_ratio:.2f})")
                        elif ratio > args.max_ratio:
                            reasons.append(f"size ratio too large ({ratio:.2f} > {args.max_ratio:.2f})")
                except OSError:
                    reasons.append("size check failed")
        else:
            if not dest_mkvs:
                reasons.append("no mkv in movies folder")
            if os.path.isdir(tagged_folder) and not src_mkvs:
                reasons.append("no mkv in tagged folder")

        if reasons:
            mis_moved.append((base, "; ".join(reasons)))

    print(f"Scanned movies folders: {len(movie_folders)}")
    print(f"Potential mis-moved: {len(mis_moved)}")
    if mis_moved:
        print("\nMis-moved list:")
        for base, reason in mis_moved:
            print(f"- {base}: {reason}")


if __name__ == "__main__":
    main()


