#!/usr/bin/env python3

import os
import argparse
from typing import List, Tuple, Optional


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


def pick_representative_mkv(mkvs: List[str]) -> Optional[str]:
    if not mkvs:
        return None
    # Pick the largest mkv as representative of the main movie file
    return max(mkvs, key=lambda p: os.path.getsize(p))


def analyze_pair(
    src_folder: str,
    dst_root: str,
    min_ratio: float,
    max_ratio: float,
) -> Tuple[str, str, Optional[float], str]:
    """
    Returns: (movie_base, status, ratio_or_None, reason)
      status ∈ {"complete", "incomplete"}
      ratio is cleaned_size / source_size when available
      reason gives concise explanation for incomplete
    """
    base = os.path.basename(src_folder.rstrip(os.sep))
    src_mkvs = find_mkvs(src_folder)
    if not src_mkvs:
        return base, "incomplete", None, "no source mkv found"
    src_mkv = pick_representative_mkv(src_mkvs)
    if src_mkv is None:
        return base, "incomplete", None, "no source mkv found"

    src_size = os.path.getsize(src_mkv)
    if src_size <= 0:
        return base, "incomplete", None, "source mkv size is zero"

    dst_folder = os.path.join(dst_root, base)
    dst_mkvs = find_mkvs(dst_folder)
    if not dst_mkvs:
        return base, "incomplete", None, "no cleaned mkv found"

    # Evaluate best target by size ratio closeness to 1.0
    best_ratio = None
    for t in dst_mkvs:
        try:
            t_size = os.path.getsize(t)
        except OSError:
            continue
        if t_size <= 0:
            continue
        ratio = t_size / src_size
        if best_ratio is None or abs(1.0 - ratio) < abs(1.0 - best_ratio):
            best_ratio = ratio

    if best_ratio is None:
        return base, "incomplete", None, "cleaned mkv has invalid size"

    if best_ratio < min_ratio:
        return base, "incomplete", best_ratio, f"cleaned too small (ratio {best_ratio:.2f} < {min_ratio:.2f})"
    if best_ratio > max_ratio:
        return base, "incomplete", best_ratio, f"cleaned too large (ratio {best_ratio:.2f} > {max_ratio:.2f})"

    return base, "complete", best_ratio, ""


def main():
    parser = argparse.ArgumentParser(
        description="Identify movies not completed from tagged → cleaned by missing files or major size changes."
    )
    parser.add_argument(
        "--src",
        default="/storage/media/tagged",
        help="Source tagged directory (default: /storage/media/tagged)",
    )
    parser.add_argument(
        "--dst",
        default="/storage/media/cleaned",
        help="Destination cleaned directory (default: /storage/media/cleaned)",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.50,
        help="Minimum acceptable cleaned_size/source_size ratio (default: 0.50)",
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=1.30,
        help="Maximum acceptable cleaned_size/source_size ratio (default: 1.30)",
    )
    args = parser.parse_args()

    src_root = os.path.abspath(args.src)
    dst_root = os.path.abspath(args.dst)

    src_folders = list_immediate_subdirs(src_root)
    total = len(src_folders)
    incomplete = []
    complete = 0

    for src_folder in sorted(src_folders, key=lambda p: os.path.basename(p).lower()):
        base, status, ratio, reason = analyze_pair(
            src_folder, dst_root, args.min_ratio, args.max_ratio
        )
        if status == "complete":
            complete += 1
        else:
            if ratio is None:
                incomplete.append((base, reason))
            else:
                incomplete.append((base, f"{reason}"))

    print(f"Scanned {total} source folders.")
    print(f"Complete: {complete}")
    print(f"Incomplete: {len(incomplete)}")
    if incomplete:
        print("\nIncomplete list:")
        for base, reason in incomplete:
            print(f"- {base}: {reason}")


if __name__ == "__main__":
    main()


