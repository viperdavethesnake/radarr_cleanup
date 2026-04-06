# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

A media library management toolkit for cleaning, enriching, and transcoding MKV files destined for Jellyfin. It fetches TMDB metadata, selects optimal audio/subtitle tracks, remuxes MKVs, verifies structure, and optionally transcodes to AV1. There is a parallel pipeline for movies and TV shows.

Pipeline order:
1. `batch_cleaner.py` / `tv_batch_cleaner.py` — TMDB metadata, NFO generation, MKV tag injection
2. `mkv_remux_cleanroom.py` / `tv_mkv_remux_cleanroom.py` — track selection, chapter/attachment removal
3. `verify_movies.py` — Jellyfin compatibility validation (movies only)
4. `foreign_post_processor.py` — IETF BCP 47 language normalization (foreign films only)

## Running Scripts

```bash
source .venv/bin/activate   # Python 3.14 venv at repo root

# Movie pipeline
python3 movie_cleanup/batch_cleaner.py
python3 movie_cleanup/mkv_remux_cleanroom.py
python3 movie_cleanup/verify_movies.py --scan-dir ./cleaned

# TV pipeline
python3 tv_cleanup/tv_batch_cleaner.py
python3 tv_cleanup/tv_mkv_remux_cleanroom.py

# Maintenance
./maintenance/fix_media_perms.py              # dry-run
./maintenance/fix_media_perms.py --apply      # apply with auto-sudo
./maintenance/orphaned_metadata_cleanup.py --csv report.csv
./maintenance/audit_existing_libraries.py /storage/media/movies
./maintenance/compare_movie_copies.py --new /path/new --existing /path/old

# AV1 benchmarking (requires NVIDIA GPU)
cd movie_analyzer && ./nvidia_av1_benchmark.py
./quality_analyzer.py -r results/*.json --plot --report
```

There are no automated tests. Use the helper scripts in `movie_cleanup/helpers/` and `tv_cleanup/helpers/` to spot-check and debug (e.g., `peek_mkvinfo.py`, `spot_check_movies.py`, `verify_mkv_cleanup.py`).

## Configuration

Scripts load configuration from `.env` (not committed; see `.env.example`). All path and tool settings have sensible defaults but are overrideable:

| Variable | Purpose |
|---|---|
| `TMDB_API_KEY` | Required — TMDB API key |
| `RC_MEDIA_BASE` | Root path for media storage |
| `RC_MEDIA_OWNER` / `RC_MEDIA_GROUP` | Ownership for `fix_media_perms.py` |
| `RC_VERIFY_SCAN_DIR`, `RC_FOREIGN_DIR`, `RC_CLEANED_DIR` | Movie script paths |
| `RC_MOVIES_DIR`, `RC_WORK_DIR`, `RC_OUTPUT_DIR` | AV1 analyzer paths |
| `RC_FFMPEG_BIN`, `RC_FFPROBE_BIN`, `RC_FFMPEG_PREFIX` | Custom FFmpeg locations |

## System Dependencies

- **MKVToolNix**: `mkvmerge`, `mkvpropedit`, `mkvinfo`
- **FFmpeg**: with AV1 + VMAF support (for `movie_analyzer/`)
- **setfacl** (package `acl`) — for `fix_media_perms.py`
- **nvidia-smi** + CUDA — for `nvidia_av1_benchmark.py`

Python packages: `requests`, `python-dotenv`, `numpy`, `matplotlib` (see `requirements.txt`).

## Architecture

**Concurrency**: All major scripts use `ThreadPoolExecutor`. Worker counts are tuned per workload: 8 for network-bound (TMDB), 12 for I/O/remux-bound. Scripts register `SIGINT`/`SIGTERM` handlers for graceful shutdown.

**File routing**: Failed files go to `./failed/` or `./failed_tv/`. Files needing manual review (multiple video tracks, no acceptable audio) go to `./review/`.

**Metadata formats**:
- `movie.nfo` — Jellyfin-compatible XML
- `metadata.json` — intermediate processing state
- `tags.xml` — MKV tag injection via `mkvpropedit`
- `poster.jpg` — cover art downloaded from TMDB

**Output naming**:
- Movies: `Movie_Title_(Year)_imdbid.mkv` inside `Movie_Title_(Year)/`
- TV episodes: `Show_Name_S01E01_Episode_[2160p_HEVC_EAC3].mkv`
- Underscores for spaces (Jellyfin/Infuse compatibility)

**Track selection rules**:
- Audio: English preferred, commentary excluded. Codec priority: TrueHD > DTS-HD > DTS > AC3 > EAC3 > AAC
- Subtitles: SRT preferred; SDH/HI/forced excluded
- Video: Multiple video tracks → moved to `./review/`

**Logging**: Dual output (console + `./logs/*.log`), timestamped, emoji status indicators.

## Subdirectory Layout

```
movie_cleanup/      Main movie pipeline + helpers/
tv_cleanup/         Main TV pipeline + helpers/
movie_analyzer/     AV1 GPU benchmarking and quality analysis
maintenance/        Read-only reporting and permission tools
```
