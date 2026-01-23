# GPU-Accelerated AV1 Encoding Pipeline

**Author:** ViperDavetheSnake (microbarley@gmail.com)

Advanced AV1 encoding pipeline using Nvidia GPU hardware acceleration for high-speed, high-quality video transcoding.

## 🚀 Overview

This pipeline leverages **Nvidia RTX 5060 Ti** hardware acceleration for AV1 encoding, providing:
- **10-50x faster** encoding compared to CPU-based solutions
- **Scientific quality benchmarking** with VMAF, PSNR, and SSIM metrics
- **Automated optimization** to find the best quality/speed/size balance
- **Comprehensive analysis tools** for encoding performance

## 🏗️ Architecture

```
GPU AV1 Pipeline:
/storage/media/servarr/cleaned → [Analysis] → [Sample Extraction] → [GPU Encoding] → [Quality Analysis] → /space/media/av1
```

## 📁 Working Environment

- **Repo**: `/home/david/git/radarr_cleanup/movie_analyzer/` (scripts and local results)
  - `samples/` - Extracted test samples (local)
  - `results/` - Benchmark results and analysis (local)
- **Storage**:
  - `/storage/media/servarr/cleaned/` - Source movies (ready for encoding)
  - `/space/media/working/` - Fast NVMe working space 
  - `/space/media/av1/` - Final AV1 output files

## 🎯 Hardware Requirements

- **GPU**: Nvidia RTX 40/50 series with AV1 hardware encoding
- **Storage**: Fast NVMe storage for working directory
- **Memory**: 16GB+ system RAM recommended
- **VRAM**: 8GB+ GPU memory for concurrent encoding

## 🛠️ Available Tools

### 📊 Benchmark Suite (`nvidia_av1_benchmark.py`)
Comprehensive quality and performance testing:
- Tests multiple presets (p4-p7) and CQ values (20-32)
- Extracts samples from different scene types
- Measures VMAF, PSNR, SSIM quality metrics
- Monitors GPU utilization and encoding speed
- Generates scientific recommendations

### 🔍 Quality Analyzer (`quality_analyzer.py`)
Advanced quality analysis and visualization:
- Detailed VMAF scoring with percentiles
- Visual comparison frame extraction
- Quality vs compression plots
- HTML reports with recommendations

## ⚡ Nvidia AV1 Encoder Features

**Hardware Acceleration**: `av1_nvenc` encoder
**Presets**: p1 (fastest) → p7 (best quality)
**Rate Control**: CQ (Constant Quality) recommended
**Advanced Features**:
- Spatial/Temporal Adaptive Quantization
- 2-pass encoding support
- 10-bit encoding capability
- B-frame optimization

## 🔥 Quick Start

### 1. Verify Source Movies
```bash
# Check available cleaned movies ready for encoding
ls -la /storage/media/servarr/cleaned/
```

### Python Dependencies
These scripts use the repo's shared Python dependencies:

```bash
cd /home/david/git/radarr_cleanup
python3 -m pip install -r requirements.txt
```

### 2. Run Benchmark Analysis
```bash
cd /home/david/git/radarr_cleanup/movie_analyzer
./nvidia_av1_benchmark.py
```

### 3. Analyze Results
```bash
./quality_analyzer.py -r results/nvidia_av1_benchmark_*.json --plot --report
```

### 4. Apply Optimal Settings
Use the recommended configuration for batch encoding.

## 📈 Typical Results

**RTX 5060 Ti Performance** (based on initial testing):
- **Speed**: 2-4x realtime encoding
- **Quality**: VMAF 95+ (visually transparent)
- **Compression**: 30-50% size reduction vs H.264/HEVC
- **Power**: ~100-150W GPU utilization

## 🎯 Quality Targets

- **VMAF ≥ 95**: Visually transparent quality (recommended)
- **VMAF 90-95**: Good quality with minor artifacts
- **VMAF < 90**: Noticeable quality degradation (avoid)

## 📊 Optimization Strategy

1. **Benchmark first** - Don't guess, measure
2. **Target VMAF 95+** - Ensure visual transparency
3. **Balance speed vs quality** - Use fastest preset that meets quality threshold
4. **Monitor GPU utilization** - Ensure hardware is fully utilized
5. **Validate results** - Spot-check encoded files

## 🔧 Configuration Examples

### Fast & High Quality (Recommended)
```bash
ffmpeg -hwaccel cuda -i input.mkv -c:v av1_nvenc -preset p5 -cq 26 -spatial-aq 1 -temporal-aq 1 -c:a copy output.mkv
```

### Maximum Quality
```bash
ffmpeg -hwaccel cuda -i input.mkv -c:v av1_nvenc -preset p7 -cq 20 -multipass fullres -spatial-aq 1 -temporal-aq 1 -c:a copy output.mkv
```

### Maximum Speed
```bash
ffmpeg -hwaccel cuda -i input.mkv -c:v av1_nvenc -preset p4 -cq 30 -c:a copy output.mkv
```

## 📝 Notes

- **Always benchmark first** - Different content may need different settings
- **GPU memory matters** - Monitor VRAM usage for concurrent encoding
- **Quality validation** - Use VMAF scores, not just file size
- **Storage performance** - NVMe storage significantly improves encoding speed
- **Power efficiency** - GPU encoding uses less total system power than CPU

## 🔄 Workflow

1. **Setup**: Copy movies to `/space/media/movies/`
2. **Benchmark**: Run quality/performance analysis
3. **Optimize**: Find best preset/CQ combination
4. **Batch Encode**: Apply settings to full collection
5. **Validate**: Spot-check quality and compatibility
6. **Deploy**: Replace originals with AV1 versions

## 🎉 Benefits

- **90%+ encoding speed improvement** vs CPU
- **Scientific quality validation** vs guesswork
- **Consistent results** across different content types
- **Future-proof format** with broad compatibility
- **Significant storage savings** with maintained quality