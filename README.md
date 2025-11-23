# Radarr Cleanup Tools

A collection of tools for managing and optimizing movie and TV collections.

## 📁 Repository Structure

```
radarr_cleanup/
├── movie_cleanup/              # MKV processing and metadata tools for Movies
│   ├── batch_cleaner.py        # Extract metadata, clean names, inject tags
│   ├── mkv_remux_cleanroom.py  # Track selection and remuxing
│   ├── foreign_post_processor.py # Post-processing for foreign films
│   ├── helpers/                # Helper scripts and utilities
│   └── README.md               # Detailed documentation
├── tv_cleanup/                 # Tools for TV Show management
│   ├── tv_batch_cleaner.py     # TV show metadata and cleaning
│   ├── tv_mkv_remux_cleanroom.py # TV show remuxing
│   └── README.md               # TV cleanup documentation
├── movie_analyzer/             # AV1 transcoding and analysis tools
│   ├── nvidia_av1_benchmark.py # AV1 encoder benchmarking
│   ├── quality_analyzer.py     # VMAF quality analysis
│   ├── results/                # Analysis results
│   └── README.md               # Analysis documentation
└── README.md                   # This file
```

## 🎬 Collection Management

### Movie Processing (`movie_cleanup/`)
Tools for processing existing Movie MKV files:
- **Metadata Extraction**: From NFO files and TMDB API
- **Name Cleaning**: Standardize folder and file names
- **Tag Injection**: Add collection and metadata tags
- **Track Selection**: Choose best audio/subtitle tracks
- **Remuxing**: Create clean, optimized MKV files

### TV Processing (`tv_cleanup/`)
Tools for processing TV Show files:
- **Episode Cleaning**: Standardize episode naming
- **Batch Processing**: Handle entire seasons or series
- **Remuxing**: Optimize tracks for TV episodes

### AV1 Transcoding & Analysis (`movie_analyzer/`)
Tools for transcoding to AV1 format and quality benchmarking:
- **AV1 Benchmarking**: Test different encoders (SVT-AV1, NVENC)
- **Quality Analysis**: VMAF scoring and comparison
- **Batch Processing**: Generate and run transcoding scripts

## 🚀 Quick Start

### Movie Processing
```bash
cd movie_cleanup
./batch_cleaner.py
./mkv_remux_cleanroom.py
```

### TV Processing
```bash
cd tv_cleanup
./tv_batch_cleaner.py
```

### Analysis
```bash
cd movie_analyzer
./nvidia_av1_benchmark.py
```

## 🔧 Requirements

- Python 3.7+
- FFmpeg with AV1 and VMAF support
- MKVToolNix (`mkvmerge`, `mkvpropedit`)
- TMDB API key (for metadata)

## 📝 Notes

- Tools are independent and can be used separately
- MKV processing preserves original files until verified
- AV1 transcoding creates new files (original preserved)
- All tools support graceful interruption and error handling



 