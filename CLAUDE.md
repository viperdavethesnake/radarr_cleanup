# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

A media library management toolkit for cleaning, enriching, and transcoding MKV files destined for Jellyfin. It fetches TMDB metadata, selects optimal audio/subtitle tracks, remuxes MKVs, verifies structure, and optionally transcodes to AV1. There is a parallel pipeline for movies and TV shows.

Pipeline order:
1. `batch_cleaner.py` / `tv_batch_cleaner.py` — TMDB metadata, NFO generation, MKV tag injection. English-original films are staged into `./tagged/`; foreign-original films (TMDB `original_language != 'en'`) are staged into `./foreign/` with sidecars but no track selection.
2. `mkv_remux_cleanroom.py` / `tv_mkv_remux_cleanroom.py` — track selection, chapter/attachment removal. The movie variant scans **both** `./tagged/` (English-preference rules) and `./foreign/` (original-language audio, English text-or-PGS sub, tag injection from sidecar tags.xml).
3. `verify_movies.py` — Jellyfin compatibility validation (movies only)
4. `foreign_post_processor.py` — legacy IETF BCP 47 language normalization (superseded by mkv_remux_cleanroom's foreign path; kept for reference)

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
./maintenance/audit_library.py /storage/media/movies --out /tmp/audit   # full 10-check audit
./maintenance/audit_decode_integrity.py --workers 3 --threads 4         # ffmpeg full-decode pass; --resume <jsonl> to continue

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

**Concurrency**: All major scripts use `ThreadPoolExecutor`. Worker counts are tuned per workload: 8 for network-bound (TMDB metadata), 4 for the remux stage (`MAX_WORKERS` in **both** `mkv_remux_cleanroom.py` and `tv_mkv_remux_cleanroom.py`). The remux stage is **storage-bound, not CPU-bound** — each `mkvmerge` is a demux/remux of a 40–90 GB file, so the bottleneck is ZFS pool bandwidth, not cores. Running too many in parallel splits that one pool N ways, collapses per-job throughput, and trips the 1800s per-job timeout (this happened at 12-way: 9 of 16 jobs timed out and landed in `./failed/`). Keep both at 4 so each job gets enough bandwidth to finish well under the timeout and leaves I/O headroom for co-resident Jellyfin/Frigate/Ollama. More threads do **not** make remux faster here. Scripts register `SIGINT`/`SIGTERM` handlers for graceful shutdown.

**File routing**: Failed files go to `./failed/` or `./failed_tv/`. Files needing manual review (multiple video tracks, no acceptable audio) go to `./review/` or `./review_tv/`. Foreign-language sources are staged at `./foreign/` or `./foreign_tv/`.

**Metadata formats**:
- `movie.nfo` / `tvshow.nfo` / per-episode `<episodedetails>` NFO — Jellyfin-compatible XML
- `metadata.json` — intermediate processing state
- `tags.xml` — MKV tag injection via `mkvpropedit`; for TV, built per-episode (show + episode targets) and applied during batch_cleaner

> **mkvpropedit attachment-delete gotcha**: `strip_attachments` deletes cover-art attachments with the `=<uid>` selector (`--delete-attachment ={uid}`), **not** `uid:<uid>`. `uid:` is not a valid mkvpropedit selector and fails with exit 2 ("Invalid selector"); it also can't represent UIDs above signed-int64 max. Valid forms are a bare attachment id, `=<uid>`, or `name:`/`mime-type:`. Most sources have no attachments so the delete path rarely runs — the bug only surfaces on Remux releases that embed a `cover.jpg`.
- `poster.jpg` / `fanart.jpg` — artwork downloaded from TMDB

**Output naming**:
- Movies: `Movie_Title_(Year)_[2160p_hevc_eac3].mkv` inside `Movie_Title_(Year)/` (technical suffix added at remux; IMDb ID lives in embedded MKV tags, not the filename)
- TV episodes: `Show_Name_SxxExx_Episode_Title_[2160p_hevc_eac3].mkv` inside `Show_Name_(Year)/Season NN/`
- Underscores for spaces (Jellyfin/Infuse compatibility)

**Track selection rules**:
- Audio: English preferred, commentary/audio-description excluded. Codec priority: TrueHD > DTS-HD > DTS > EAC3 > AC3 > FLAC > AAC > MP3
- Subtitles: SRT preferred; SDH/HI/forced/commentary excluded
- Video: Multiple video tracks → moved to review directory

**Logging**: Dual output (console + `./logs/*.log`), timestamped, emoji status indicators.

**Source of truth**: MKV embedded tags are the authoritative identity for each title. For movies, those are the IMDb/TMDB IDs. For TV, each episode carries the show's TVDB/TMDB/IMDb IDs *and* per-episode S/E + episode TMDB ID. NFOs and artwork are derived from those tags and can be regenerated via `maintenance/regenerate_nfos.py`.

## Maintenance Script Conventions

All scripts in `maintenance/` follow these patterns:
- Dry-run by default (`--audit`); destructive ops require `--run` or `--apply`
- `--json` / `--csv` export, `--limit N` for quick testing
- `ThreadPoolExecutor` with graceful `SIGINT`/`SIGTERM` shutdown
- Errors accumulate and report at the end — never stop mid-run on a single failure
- Symlinks skipped in all directory walks

`audit_decode_integrity.py` is a long-running CPU-bound audit (full ffmpeg decode of every MKV, multi-day for a large library). It departs from a few defaults by design: no dry-run flag (it's read-only), `--resume <jsonl>` to skip files already recorded as OK/ERRORS/TIMEOUT in a prior run, JSONL appended as each decode completes so partial findings survive interruption, and conservative parallelism tuned to leave Jellyfin headroom (default `--workers 3 --threads 4` = 12 of 20 logical cores on this box). Software decode is intentional — NVDEC silently conceals the HEVC slice / H.264 mmco errors this script exists to find.

## Jellyfin Setup

- **Server**: Docker on macvlan at `192.168.36.200:8096` (barley-nas, `192.168.36.40`)
- **Libraries**: Movies (`/storage/media/movies`), Documentaries (`/storage/media/documentaries`)
- **Metadata**: NFO reader enabled, NFO saver disabled, remote image fetchers disabled
- **Collections**: `AutomaticallyAddToCollection: true`
- **Artwork**: `poster.jpg` + `fanart.jpg` stored alongside media files
- **Hardware transcoding**: NVENC via RTX 5060 Ti (16 GB), tone mapping enabled
- **Trickplay/chapters**: generated but stored in Jellyfin data dir (not alongside media)

## Radarr Integration

- **URL**: `http://192.168.36.195:7878` (`.env` `RADARR_URL`)
- **API key**: in `.env` as `RADARR_API_KEY`. `radarr_upgrade_push.py` reads `RADARR_URL`/`RADARR_API_KEY`/`RADARR_PROFILE_ID`/`RADARR_ROOT_FOLDER` from `.env` (live values are baked in as fallback defaults).
- **Quality profile "Mine" (id=7)**: upgrades enabled, cutoff = Remux-2160p, allows Bluray-1080p / Remux-1080p / WEBDL-2160p / WEBRip-2160p / Bluray-2160p / Remux-2160p. Custom format scores: AV1=+100, h265=+75, h264=+50, Unwanted=-100.
- **Root folder**: `/servarr/servarr/movies`
- **Indexers**: NZBgeek + Nzb.su (Usenet, both RSS-enabled)

### Workflow: Add net-new or upgrade movies to Radarr

Use `maintenance/radarr_upgrade_push.py`. It reads the output of `compare_movie_copies.py`, extracts IMDb IDs for net-new and KEEP-NEW movies, and adds them to Radarr with profile "Mine" + immediate search.

```bash
# 1. Run the library comparison (both sides are remote SSH hosts)
source .venv/bin/activate
python3 maintenance/compare_movie_copies.py \
  --path-a /storage/media/movies --ssh-a david@192.168.33.40 \
  --path-b /storage/media/movies --ssh-b david@192.168.36.40 \
  --details > /tmp/compare_output.txt

# 2. Preview what will be added to Radarr
python3 maintenance/radarr_upgrade_push.py --dry-run

# 3. Push to Radarr (adds movies + triggers search immediately)
python3 maintenance/radarr_upgrade_push.py
```

#### Radarr API calls used (v3)

**Lookup a movie by IMDb ID** (resolves to TMDB metadata):
```
GET /api/v3/movie/lookup?term=imdb:tt0076759
```
Returns array; take `[0]`. Key fields: `title`, `year`, `tmdbId`, `imdbId`, `titleSlug`, `images`.

**Add a movie**:
```
POST /api/v3/movie
{
  "title":               "Star Wars",
  "titleSlug":           "star-wars",
  "year":                1977,
  "tmdbId":              11,
  "imdbId":              "tt0076759",
  "qualityProfileId":    7,
  "rootFolderPath":      "/servarr/servarr/movies",
  "monitored":           true,
  "minimumAvailability": "released",
  "images":              [...],          // from lookup response
  "addOptions":          { "searchForMovie": true }
}
```
Returns the created movie object including `id`.

**List all movies** (to check what's already in Radarr):
```
GET /api/v3/movie
```
Returns array of all movies. Filter by `imdbId` field to avoid duplicates.

**Trigger search for specific movies** (bulk):
```
POST /api/v3/command
{ "name": "MoviesSearch", "movieIds": [1, 2, 3] }
```

**Auth**: all requests require header `X-Api-Key: <key>`.

## Subdirectory Layout

```
movie_cleanup/      Main movie pipeline + helpers/
tv_cleanup/         Main TV pipeline + helpers/
movie_analyzer/     AV1 GPU benchmarking and quality analysis
maintenance/        Read-only reporting and permission tools
```
