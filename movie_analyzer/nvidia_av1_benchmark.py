#!/usr/bin/env python3
"""
Nvidia AV1 Encoding Benchmark Tool
Comprehensive quality and performance testing for GPU-accelerated AV1 encoding.
"""

import subprocess
import json
import time
import os
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys

# Runtime config (override via env on each server)
REPO_ROOT = Path(__file__).resolve().parents[1]
FFMPEG_PREFIX = Path(os.getenv("RC_FFMPEG_PREFIX", str(REPO_ROOT / "ffmpeg-build")))
VMAF_LIB_DIR = Path(os.getenv("RC_VMAF_LIB_DIR", str(REPO_ROOT / "vmaf-install/lib/x86_64-linux-gnu")))


def resolve_binary(explicit_env: str, fallback_path: Path, system_name: str) -> str:
    override = os.getenv(explicit_env)
    if override:
        return override
    if fallback_path.exists():
        return str(fallback_path)
    found = shutil.which(system_name)
    return found if found else str(fallback_path)


FFMPEG_BIN = resolve_binary("RC_FFMPEG_BIN", FFMPEG_PREFIX / "bin/ffmpeg", "ffmpeg")
FFPROBE_BIN = resolve_binary("RC_FFPROBE_BIN", FFMPEG_PREFIX / "bin/ffprobe", "ffprobe")
CUSTOM_LD_PATH = os.getenv("RC_LD_LIBRARY_PATH", f"{FFMPEG_PREFIX}/lib:{VMAF_LIB_DIR}")

# Configuration
WORK_DIR = Path(os.getenv("RC_WORK_DIR", "/space/media/working"))  # Fast NVMe working space
MOVIES_DIR = Path(os.getenv("RC_MOVIES_DIR", "/storage/media/servarr/cleaned"))  # Source: cleaned movies
OUTPUT_DIR = Path(os.getenv("RC_OUTPUT_DIR", "/space/media/av1"))  # Destination: final AV1 files
RESULTS_DIR = Path("./results")                  # Local: benchmark results in repo
SAMPLES_DIR = Path("./samples")                  # Local: test samples in repo

# Benchmark configurations
PRESETS_TO_TEST = ['p4', 'p5', 'p6', 'p7']  # Focus on quality presets
CQ_VALUES = [20, 23, 26, 28, 30, 32]  # Quality range
SAMPLE_DURATION = 60  # seconds
SAMPLE_SCENES = {
    'high_motion': {'start': 300, 'description': 'Action/high motion scene'},
    'low_motion': {'start': 600, 'description': 'Dialogue/low motion scene'},
    'complex': {'start': 900, 'description': 'Complex textures/details'}
}

class NvidiaAV1Benchmark:
    def __init__(self):
        self.setup_directories()
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self.get_system_info(),
            'test_configs': [],
            'samples': {},
            'results': []
        }
        self.presets_to_test = PRESETS_TO_TEST
        self.cq_values = CQ_VALUES
    
    def setup_directories(self):
        """Create necessary directories"""
        for dir_path in [WORK_DIR, OUTPUT_DIR, RESULTS_DIR, SAMPLES_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for organization
        (SAMPLES_DIR / "extracts").mkdir(exist_ok=True)
        (WORK_DIR / "encoded").mkdir(exist_ok=True)
        (WORK_DIR / "quality").mkdir(exist_ok=True)
    
    def get_system_info(self):
        """Gather system information"""
        try:
            # GPU info
            gpu_info = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', 
                                     '--format=csv,noheader,nounits'], 
                                    capture_output=True, text=True)
            
            # FFmpeg version (same binary used by benchmark)
            ffmpeg_info = subprocess.run([FFMPEG_BIN, '-version'],
                                       capture_output=True, text=True)
            
            return {
                'gpu': gpu_info.stdout.strip() if gpu_info.returncode == 0 else 'Unknown',
                'ffmpeg_version': ffmpeg_info.stdout.split('\n')[0] if ffmpeg_info.returncode == 0 else 'Unknown',
                'ffmpeg_bin': FFMPEG_BIN,
                'ffprobe_bin': FFPROBE_BIN,
                'ld_library_path': CUSTOM_LD_PATH,
                'movies_dir': str(MOVIES_DIR),
                'work_dir': str(WORK_DIR),
                'output_dir': str(OUTPUT_DIR),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_video_info(self, filepath):
        """Get detailed video information using ffprobe"""
        cmd = [
            FFPROBE_BIN, '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', str(filepath)
        ]
        
        try:
            # Set custom library path
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = CUSTOM_LD_PATH
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            data = json.loads(result.stdout)
            
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
            if not video_stream:
                return None
            
            format_info = data['format']
            
            return {
                'filename': filepath.name,
                'duration': float(format_info.get('duration', 0)),
                'size_bytes': int(format_info.get('size', 0)),
                'size_mb': int(format_info.get('size', 0)) / (1024 * 1024),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'codec': video_stream.get('codec_name'),
                'width': video_stream.get('width'),
                'height': video_stream.get('height'),
                'fps': self.parse_fps(video_stream.get('r_frame_rate', '0/1')),
                'pixel_format': video_stream.get('pix_fmt'),
                'profile': video_stream.get('profile'),
                'level': video_stream.get('level')
            }
        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
            return None
    
    def parse_fps(self, fps_str):
        """Parse frame rate string to float"""
        try:
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                return num / den if den != 0 else 0
            return float(fps_str)
        except:
            return 0
    
    def extract_sample(self, source_file, scene_type, scene_config):
        """Extract a sample clip for testing"""
        start_time = scene_config['start']
        output_file = SAMPLES_DIR / "extracts" / f"{source_file.stem}_{scene_type}.mkv"
        
        cmd = [
            FFMPEG_BIN, '-y', '-ss', str(start_time), '-i', str(source_file),
            '-t', str(SAMPLE_DURATION), '-c', 'copy', str(output_file)
        ]
        
        try:
            print(f"  Extracting {scene_type} sample from {source_file.name}...")
            # Set custom library path
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = CUSTOM_LD_PATH
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            
            # Verify the sample
            sample_info = self.get_video_info(output_file)
            if sample_info and sample_info['duration'] > 30:  # At least 30 seconds
                return output_file, sample_info
            else:
                print(f"  Warning: Sample too short or invalid: {output_file}")
                return None, None
                
        except subprocess.CalledProcessError as e:
            print(f"  Error extracting sample: {e}")
            return None, None
    
    def encode_sample(self, sample_file, preset, cq_value):
        """Encode a sample with specific settings"""
        config_name = f"{sample_file.stem}_p{preset}_cq{cq_value}"
        output_file = WORK_DIR / "encoded" / f"{config_name}.mkv"
        
        cmd = [
            FFMPEG_BIN, '-y', '-hwaccel', 'cuda', '-i', str(sample_file),
            '-c:v', 'av1_nvenc', '-preset', preset, '-cq', str(cq_value),
            '-spatial-aq', '1', '-temporal-aq', '1',
            '-c:a', 'copy', str(output_file)
        ]
        
        print(f"    Encoding with preset {preset}, CQ {cq_value}...")
        
        try:
            start_time = time.time()
            
            # Monitor GPU during encoding
            gpu_monitor = self.start_gpu_monitoring()
            
            # Set custom library path
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = CUSTOM_LD_PATH
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            
            end_time = time.time()
            encoding_time = end_time - start_time
            
            # Stop GPU monitoring
            gpu_stats = self.stop_gpu_monitoring(gpu_monitor)
            
            # Get output file info
            output_info = self.get_video_info(output_file)
            
            if output_info:
                return {
                    'config': f"{preset}_cq{cq_value}",
                    'preset': preset,
                    'cq': cq_value,
                    'output_file': str(output_file),
                    'encoding_time': encoding_time,
                    'output_size_mb': output_info['size_mb'],
                    'gpu_stats': gpu_stats,
                    'success': True
                }
            else:
                return {'config': f"{preset}_cq{cq_value}", 'success': False, 'error': 'Invalid output'}
                
        except subprocess.CalledProcessError as e:
            print(f"    Encoding failed: {e}")
            return {
                'config': f"{preset}_cq{cq_value}",
                'success': False,
                'error': str(e),
                'stderr': e.stderr if hasattr(e, 'stderr') else ''
            }
    
    def start_gpu_monitoring(self):
        """Start monitoring GPU utilization"""
        return {
            'start_time': time.time(),
            'monitoring': True
        }
    
    def stop_gpu_monitoring(self, monitor_data):
        """Stop GPU monitoring and return stats"""
        try:
            # Get current GPU stats
            result = subprocess.run([
                'nvidia-smi', '--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                stats = result.stdout.strip().split(', ')
                return {
                    'gpu_utilization': int(stats[0]),
                    'memory_used_mb': int(stats[1]),
                    'temperature': int(stats[2]),
                    'power_draw': float(stats[3]) if stats[3] != '[Not Supported]' else 0,
                    'duration': time.time() - monitor_data['start_time']
                }
        except:
            pass
        
        return {'error': 'GPU monitoring failed'}
    
    def calculate_quality_metrics(self, reference_file, encoded_file):
        """Calculate VMAF quality metric using custom FFmpeg"""
        try:
            # Generate unique log file in local directory (avoid permission issues)
            # Remove problematic characters from filename
            safe_name = Path(encoded_file).stem.replace(' ', '_').replace(',', '').replace('(', '').replace(')', '')
            log_file = Path(f"vmaf_{safe_name}_{int(time.time())}.json")
            
            # Calculate VMAF using our custom FFmpeg with full library path
            # Note: VMAF filter expects [reference][encoded] order
            vmaf_cmd = [
                FFMPEG_BIN, '-i', str(reference_file), '-i', str(encoded_file),
                '-lavfi', f'[0:v][1:v]libvmaf=log_fmt=json:log_path={log_file}:n_threads=4',
                '-f', 'null', '-'
            ]
            
            # Set custom library path
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = CUSTOM_LD_PATH
            
            print(f"    Calculating VMAF quality metrics...")
            print(f"    VMAF command: {' '.join(vmaf_cmd[:6])}...")  # Debug output
            result = subprocess.run(vmaf_cmd, capture_output=True, text=True, timeout=600, env=env)
            
            # FFmpeg VMAF often returns 0 even with successful VMAF calculation
            # Check for log file existence rather than return code
            
            if log_file.exists():
                print(f"    VMAF log file created successfully: {log_file}")
                with open(log_file, 'r') as f:
                    vmaf_data = json.load(f)
                
                pooled = vmaf_data.get('pooled_metrics', {}).get('vmaf', {})
                
                # Clean up log file
                log_file.unlink()
                
                return {
                    'vmaf_score': pooled.get('mean', 0),
                    'vmaf_min': pooled.get('min', 0),
                    'vmaf_max': pooled.get('max', 0),
                    'vmaf_std': pooled.get('std', 0),
                    'vmaf_1st_percentile': pooled.get('1st_percentile', 0),
                    'vmaf_5th_percentile': pooled.get('5th_percentile', 0),
                    'vmaf_95th_percentile': pooled.get('95th_percentile', 0),
                    'vmaf_99th_percentile': pooled.get('99th_percentile', 0),
                    'quality_method': 'VMAF'
                }
            else:
                print(f"    VMAF log file not created: {log_file}")
                print(f"    VMAF return code: {result.returncode}")
                print(f"    VMAF stderr: {result.stderr[:300]}")
                print(f"    VMAF stdout: {result.stdout[-200:]}")
                return {'error': f'VMAF log file not created despite command completion', 'quality_method': 'VMAF'}
                
        except Exception as e:
            print(f"    VMAF calculation failed: {e}")
            return {
                'error': str(e),
                'quality_method': 'VMAF'
            }
    
    def run_sample_benchmark(self, sample_file, sample_info):
        """Run full benchmark on a single sample"""
        print(f"\n🎬 Benchmarking: {sample_file.name}")
        print(f"   Duration: {sample_info['duration']:.1f}s, Size: {sample_info['size_mb']:.1f}MB")
        
        sample_results = {
            'sample_file': str(sample_file),
            'sample_info': sample_info,
            'encodings': []
        }
        
        # Test all preset/CQ combinations
        for preset in self.presets_to_test:
            for cq in self.cq_values:
                encoding_result = self.encode_sample(sample_file, preset, cq)
                
                if encoding_result['success']:
                    # Calculate quality metrics
                    quality_metrics = self.calculate_quality_metrics(sample_file, encoding_result['output_file'])
                    encoding_result['quality'] = quality_metrics
                    
                    # Calculate compression ratio
                    compression_ratio = sample_info['size_mb'] / encoding_result['output_size_mb']
                    encoding_result['compression_ratio'] = compression_ratio
                    
                    print(f"      ✅ {preset} CQ{cq}: {encoding_result['output_size_mb']:.1f}MB "
                          f"({compression_ratio:.1f}x compression, "
                          f"{encoding_result['encoding_time']:.1f}s)")
                    
                    if 'vmaf_score' in quality_metrics:
                        print(f"         VMAF: {quality_metrics['vmaf_score']:.1f}")
                
                sample_results['encodings'].append(encoding_result)
        
        return sample_results
    
    def save_results(self):
        """Save benchmark results to JSON"""
        results_file = RESULTS_DIR / f"nvidia_av1_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📊 Results saved to: {results_file}")
        return results_file
    
    def run_benchmark(self, source_files=None):
        """Run the complete benchmark suite"""
        print("🚀 Starting Nvidia AV1 Encoding Benchmark")
        print(f"📂 Source movies: {MOVIES_DIR}")
        print(f"🔧 Working space: {WORK_DIR}")
        print(f"📊 Results saved to: {RESULTS_DIR}")
        print(f"🎯 Testing presets: {self.presets_to_test}")
        print(f"🎚️ Testing CQ values: {self.cq_values}")
        
        # Find source files if not provided
        if not source_files:
            source_files = list(MOVIES_DIR.glob("**/*.mkv"))
            if not source_files:
                print("❌ No MKV files found in movies directory!")
                return None
        
        print(f"🎬 Found {len(source_files)} source files")
        
        # Extract samples for testing
        samples = {}
        for source_file in source_files[:3]:  # Limit to first 3 files for initial testing
            print(f"\n📄 Processing: {source_file.name}")
            source_info = self.get_video_info(source_file)
            
            if not source_info or source_info['duration'] < 1200:  # Need at least 20 minutes
                print(f"  ⚠️ Skipping: file too short or invalid")
                continue
            
            # Extract different scene types
            file_samples = {}
            for scene_type, scene_config in SAMPLE_SCENES.items():
                if source_info['duration'] > scene_config['start'] + SAMPLE_DURATION:
                    sample_file, sample_info = self.extract_sample(source_file, scene_type, scene_config)
                    if sample_file:
                        file_samples[scene_type] = {'file': sample_file, 'info': sample_info}
            
            if file_samples:
                samples[source_file.name] = file_samples
        
        if not samples:
            print("❌ No valid samples extracted!")
            return None
        
        self.results['samples'] = {k: {scene: str(v['file']) for scene, v in scenes.items()} 
                                  for k, scenes in samples.items()}
        
        # Run benchmarks on samples with parallel processing
        print(f"\n🔥 Running encoding benchmarks...")
        
        # Prepare all benchmark tasks
        benchmark_tasks = []
        for source_name, file_samples in samples.items():
            for scene_type, sample_data in file_samples.items():
                benchmark_tasks.append({
                    'source_name': source_name,
                    'scene_type': scene_type,
                    'sample_file': sample_data['file'],
                    'sample_info': sample_data['info']
                })
        
        parallel_streams = getattr(self, 'parallel_streams', 3)
        max_workers = min(parallel_streams, len(benchmark_tasks))
        print(f"📊 Processing {len(benchmark_tasks)} samples with {max_workers} parallel streams...")
        
        # Run benchmarks with configurable parallelism
        # This utilizes GPU better while avoiding I/O saturation
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.run_sample_benchmark, task['sample_file'], task['sample_info']): task
                for task in benchmark_tasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    result['source_file'] = task['source_name']
                    result['scene_type'] = task['scene_type']
                    self.results['results'].append(result)
                    print(f"✅ Completed: {task['source_name']} - {task['scene_type']}")
                except Exception as e:
                    print(f"❌ Failed: {task['source_name']} - {task['scene_type']}: {e}")
        
        # Save results
        results_file = self.save_results()
        
        # Generate summary
        self.generate_summary()
        
        return results_file
    
    def generate_summary(self):
        """Generate a summary of benchmark results"""
        print("\n" + "="*60)
        print("📊 BENCHMARK SUMMARY")
        print("="*60)
        
        if not self.results['results']:
            print("No results to summarize")
            return
        
        # Collect all successful encodings
        all_encodings = []
        for sample_result in self.results['results']:
            for encoding in sample_result['encodings']:
                if encoding['success'] and 'quality' in encoding and 'vmaf_score' in encoding['quality']:
                    encoding['sample'] = f"{sample_result['source_file']}_{sample_result['scene_type']}"
                    all_encodings.append(encoding)
        
        if not all_encodings:
            print("No successful encodings with quality metrics")
            return
        
        print(f"Total successful encodings: {len(all_encodings)}")
        
        # Find best configurations
        best_quality = max(all_encodings, key=lambda x: x['quality']['vmaf_score'])
        best_compression = max(all_encodings, key=lambda x: x['compression_ratio'])
        best_speed = min(all_encodings, key=lambda x: x['encoding_time'])
        
        print(f"\n🏆 Best Quality (VMAF): {best_quality['config']} - "
              f"VMAF {best_quality['quality']['vmaf_score']:.1f}")
        print(f"🗜️ Best Compression: {best_compression['config']} - "
              f"{best_compression['compression_ratio']:.1f}x")
        print(f"⚡ Fastest Encoding: {best_speed['config']} - "
              f"{best_speed['encoding_time']:.1f}s")
        
        # Recommendations based on VMAF > 95 threshold
        high_quality = [e for e in all_encodings if e['quality']['vmaf_score'] >= 95]
        if high_quality:
            # Find the best compression among high quality encodings
            recommended = max(high_quality, key=lambda x: x['compression_ratio'])
            print(f"\n🎯 RECOMMENDED: {recommended['config']}")
            print(f"   VMAF: {recommended['quality']['vmaf_score']:.1f}")
            print(f"   Compression: {recommended['compression_ratio']:.1f}x")
            print(f"   Speed: {recommended['encoding_time']:.1f}s")

def main():
    parser = argparse.ArgumentParser(description='Nvidia AV1 Encoding Benchmark')
    parser.add_argument('--source', '-s', help='Specific source file to test')
    parser.add_argument('--presets', nargs='+', default=PRESETS_TO_TEST,
                      help='Presets to test')
    parser.add_argument('--cq-values', nargs='+', type=int, default=CQ_VALUES,
                      help='CQ values to test')
    parser.add_argument('--parallel', '-p', type=int, default=3,
                      help='Number of parallel encoding streams (1-4, default: 3)')
    
    args = parser.parse_args()
    
    benchmark = NvidiaAV1Benchmark()
    
    # Update configuration if specified
    benchmark.presets_to_test = args.presets
    benchmark.cq_values = args.cq_values
    benchmark.parallel_streams = max(1, min(4, args.parallel))  # Clamp to 1-4 range
    
    source_files = None
    if args.source:
        source_path = Path(args.source)
        if source_path.exists():
            source_files = [source_path]
        else:
            print(f"❌ Source file not found: {args.source}")
            return 1
    
    results_file = benchmark.run_benchmark(source_files)
    
    if results_file:
        print(f"\n✅ Benchmark completed successfully!")
        print(f"📊 Results: {results_file}")
        return 0
    else:
        print("❌ Benchmark failed!")
        return 1

if __name__ == "__main__":
    exit(main())
