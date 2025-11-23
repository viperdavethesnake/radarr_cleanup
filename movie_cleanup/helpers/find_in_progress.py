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


def pick_largest_file(paths: List[str]) -> Optional[str]:
    if not paths:
        return None
    return max(paths, key=lambda p: os.path.getsize(p))


def has_extras(folder: str) -> Tuple[bool, List[str]]:
    required = ["movie.nfo", "poster.jpg"]
    missing = [f for f in required if not os.path.isfile(os.path.join(folder, f))]
    return (len(missing) == 0, missing)


def main():
    parser = argparse.ArgumentParser(
        description="List movies that are IN PROGRESS, scanning cleaned against tagged."
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
        "--min-ratio",
        type=float,
        default=0.50,
        help="Min acceptable cleaned_size/source_size ratio (default: 0.50)",
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=1.30,
        help="Max acceptable cleaned_size/source_size ratio (default: 1.30)",
    )
    args = parser.parse_args()

    tagged_root = os.path.abspath(args.tagged)
    cleaned_root = os.path.abspath(args.cleaned)

    cleaned_folders = list_immediate_subdirs(cleaned_root)

    in_progress = []

    for cleaned_folder in sorted(cleaned_folders, key=lambda p: os.path.basename(p).lower()):
        base = os.path.basename(cleaned_folder.rstrip(os.sep))
        tagged_folder = os.path.join(tagged_root, base)

        reasons: List[str] = []

        # If cleaned exists but tagged counterpart is gone → done (not reported)
        if not os.path.isdir(tagged_folder):
            continue

        # If tagged counterpart exists, consider in-progress
        reasons.append("source still present")

        # Check extras in cleaned
        extras_ok, missing = has_extras(cleaned_folder)
        if not extras_ok:
            reasons.append("missing extras: " + ",".join(missing))

        # Check MKVs and size delta
        cleaned_mkvs = find_mkvs(cleaned_folder)
        src_mkvs = find_mkvs(tagged_folder)

        if not cleaned_mkvs:
            reasons.append("no cleaned mkv yet")
        elif not src_mkvs:
            # Edge case: tagged exists but has no mkv; still mark in-progress with reason
            reasons.append("no source mkv in tagged")
        else:
            cleaned_main = pick_largest_file(cleaned_mkvs)
            src_main = pick_largest_file(src_mkvs)
            if cleaned_main and src_main:
                try:
                    cleaned_size = os.path.getsize(cleaned_main)
                    src_size = os.path.getsize(src_main)
                    if src_size > 0:
                        ratio = cleaned_size / src_size
                        if ratio < args.min_ratio:
                            reasons.append(f"size ratio too small ({ratio:.2f} < {args.min_ratio:.2f})")
                        elif ratio > args.max_ratio:
                            reasons.append(f"size ratio too large ({ratio:.2f} > {args.max_ratio:.2f})")
                except OSError:
                    reasons.append("size check failed")

        if reasons:
            in_progress.append((base, "; ".join(reasons)))

    print(f"Scanned cleaned folders: {len(cleaned_folders)}")
    print(f"In progress: {len(in_progress)}")
    if in_progress:
        print("\nIn-progress list:")
        for base, reason in in_progress:
            print(f"- {base}: {reason}")


if __name__ == "__main__":
    main()


