# TV Show Cleanup Scripts

This directory contains scripts for cleaning and remuxing TV shows, similar to the movie cleanup scripts but adapted for TV show structure with seasons and episodes.

Supported runtime: Python 3.13/3.14.

## Scripts

### `tv_batch_cleaner.py`
**Purpose**: Clean and organize TV shows from source directory to tagged directory

**Process**:
1. **Source**: `./tvshows/` - Raw TV show folders
2. **Destination**: `./tagged_tv/` - Cleaned and organized TV shows
3. **Failed**: `./failed_tv/` - Shows that couldn't be processed

**Features**:
- Finds all MKV files in show folders (including season subfolders)
- Extracts season/episode info from filenames (S01E02, 1x02, etc.)
- Downloads show metadata from TMDb API
- Creates proper folder structure: `Show_Name/Season_01/Episode.mkv`
- Strips tags and attachments from MKV files
- Downloads show posters
- Creates show.nfo, metadata.json, and tags.xml files
- **Enhanced naming**: Uses underscores instead of spaces for JF/Infuse compatibility
- Moves failed shows to `./failed_tv/`

**Episode Detection Patterns**:
- `S01E02` - Standard season/episode format
- `1x02` - Alternative format
- `Season 1 Episode 2` - Text format
- `1.02` or `1_02` - Simple format

### `tv_mkv_remux_cleanroom.py`
**Purpose**: Remux TV show episodes to clean up audio/video tracks

**Process**:
1. **Source**: `./tagged_tv/` - Cleaned TV shows from batch cleaner
2. **Destination**: `./cleaned_tv/` - Remuxed TV shows
3. **Failed**: `./failed_tv/` - Shows that failed remuxing

**Features**:
- Processes all episodes in a show folder
- Selects best audio track (TrueHD > DTS > EAC3 > AC3)
- Selects best subtitle track (SRT > ASS/SSA, no PGS)
- Maintains folder structure with seasons
- Copies show-level metadata files
- **Enhanced naming**: Adds technical details `[2160p_HEVC_EAC3]` to filenames
- Only deletes original if ALL episodes succeed
- Moves failed shows to `./failed_tv/`

## Usage

### Step 1: Batch Clean
```bash
cd /storage/media/servarr
python3 /home/david/git/radarr_cleanup/tv_cleanup/tv_batch_cleaner.py
```

### Step 2: Remux
```bash
cd /storage/media/servarr
python3 /home/david/git/radarr_cleanup/tv_cleanup/tv_mkv_remux_cleanroom.py
```

### Python Dependencies
These scripts use the repo's shared Python dependencies:

```bash
cd /home/david/git/radarr_cleanup
python3 -m pip install -r requirements.txt
```

## Enhanced Naming Convention

### Show Folders:
- **Before**: `Tulsa King (2022) [tvdbid-413215]`
- **After**: `Tulsa_King`

### Episode Files:
- **Before**: `Tulsa King (2022) - S03E01 - Blood and Bourbon [WEBDL-2160p][EAC3 5.1][h265]-WtF.mkv`
- **After**: `Tulsa_King_S03E01_Episode_[2160p_HEVC_EAC3].mkv`

### Benefits:
- ✅ **JF/Infuse Compatible**: No spaces in filenames
- ✅ **Technical Details**: Shows resolution, video codec, audio codec
- ✅ **Clean Structure**: Easy to read and identify
- ✅ **Consistent**: Matches movie naming convention
```

## Directory Structure

```
/storage/media/servarr/
├── tvshows/           # Source: Raw TV shows
├── tagged_tv/         # Step 1 output: Cleaned shows
├── cleaned_tv/        # Step 2 output: Remuxed shows
├── failed_tv/         # Failed shows from both steps
└── logs/              # Log files
    ├── tv_batch_cleaner_debug.log
    └── tv_remux_cleanroom_debug.log
```

## Show Structure Example

**Input**:
```
tvshows/
└── Breaking_Bad/
    ├── Season 1/
    │   ├── Breaking.Bad.S01E01.mkv
    │   └── Breaking.Bad.S01E02.mkv
    └── Season 2/
        ├── Breaking.Bad.S02E01.mkv
        └── Breaking.Bad.S02E02.mkv
```

**Output**:
```
cleaned_tv/
└── Breaking_Bad/
    ├── show.nfo
    ├── poster.jpg
    ├── metadata.json
    ├── tags.xml
    ├── Season_01/
    │   ├── Breaking_Bad_S01E01_Pilot.mkv
    │   └── Breaking_Bad_S01E02_Cat_s_in_the_Bag.mkv
    └── Season_02/
        ├── Breaking_Bad_S02E01_Seven_Thirty_Seven.mkv
        └── Breaking_Bad_S02E02_Grilled.mkv
```

## Configuration

Edit the scripts to modify:
- `MAX_WORKERS`: Number of concurrent threads
- `TMDB_API_KEY`: Your TMDb API key
- Directory paths
- Audio/subtitle preferences

## Notes

- Scripts skip non-TV directories (movies, music, etc.)
- Failed shows are moved to `./failed_tv/` for manual review
- All operations are logged with timestamps
- Scripts can be interrupted with Ctrl+C for graceful shutdown 