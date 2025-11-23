#!/usr/bin/env python3
"""
Quality Analysis Tool for AV1 Encoding
Advanced quality metrics and visual comparison tools.
"""

import subprocess
import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

class QualityAnalyzer:
    def __init__(self, results_dir="./results"):
        self.results_dir = Path(results_dir)
        self.quality_dir = self.results_dir / "quality"
        self.quality_dir.mkdir(parents=True, exist_ok=True)
    
    def calculate_comprehensive_metrics(self, reference_file, encoded_file):
        """Calculate VMAF, PSNR, and SSIM metrics"""
        metrics = {}
        
        # VMAF (most important for perceptual quality)
        vmaf_result = self.calculate_vmaf(reference_file, encoded_file)
        if 'error' not in vmaf_result:
            metrics.update(vmaf_result)
        
        # PSNR
        psnr_result = self.calculate_psnr(reference_file, encoded_file)
        if 'error' not in psnr_result:
            metrics.update(psnr_result)
        
        # SSIM
        ssim_result = self.calculate_ssim(reference_file, encoded_file)
        if 'error' not in ssim_result:
            metrics.update(ssim_result)
        
        return metrics
    
    def calculate_vmaf(self, reference_file, encoded_file):
        """Calculate VMAF score with detailed metrics"""
        vmaf_log = self.quality_dir / f"vmaf_{Path(encoded_file).stem}.json"
        
        try:
            cmd = [
                'ffmpeg', '-i', str(encoded_file), '-i', str(reference_file),
                '-lavfi', f'[0:v][1:v]libvmaf=log_fmt=json:log_path={vmaf_log}:n_threads=4',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if vmaf_log.exists():
                with open(vmaf_log, 'r') as f:
                    vmaf_data = json.load(f)
                
                pooled = vmaf_data.get('pooled_metrics', {}).get('vmaf', {})
                
                return {
                    'vmaf_mean': pooled.get('mean', 0),
                    'vmaf_min': pooled.get('min', 0),
                    'vmaf_max': pooled.get('max', 0),
                    'vmaf_std': pooled.get('std', 0),
                    'vmaf_1st_percentile': pooled.get('1st_percentile', 0),
                    'vmaf_5th_percentile': pooled.get('5th_percentile', 0),
                    'vmaf_95th_percentile': pooled.get('95th_percentile', 0),
                    'vmaf_99th_percentile': pooled.get('99th_percentile', 0),
                    'vmaf_log_file': str(vmaf_log)
                }
            else:
                return {'error': 'VMAF log file not created'}
                
        except Exception as e:
            return {'error': f'VMAF calculation failed: {e}'}
    
    def calculate_psnr(self, reference_file, encoded_file):
        """Calculate PSNR metrics"""
        try:
            cmd = [
                'ffmpeg', '-i', str(encoded_file), '-i', str(reference_file),
                '-lavfi', '[0:v][1:v]psnr=stats_file=/tmp/psnr.log',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Parse PSNR from stderr
            psnr_line = None
            for line in result.stderr.split('\n'):
                if 'PSNR' in line and 'average:' in line:
                    psnr_line = line
                    break
            
            if psnr_line:
                # Extract PSNR values: typically looks like "PSNR y:45.123 u:48.456 v:47.789 average:45.678 min:40.123 max:50.456"
                parts = psnr_line.split()
                psnr_data = {}
                
                for part in parts:
                    if ':' in part:
                        key, value = part.split(':')
                        try:
                            psnr_data[f'psnr_{key}'] = float(value)
                        except ValueError:
                            continue
                
                return psnr_data
            else:
                return {'error': 'PSNR values not found in output'}
                
        except Exception as e:
            return {'error': f'PSNR calculation failed: {e}'}
    
    def calculate_ssim(self, reference_file, encoded_file):
        """Calculate SSIM metrics"""
        try:
            cmd = [
                'ffmpeg', '-i', str(encoded_file), '-i', str(reference_file),
                '-lavfi', '[0:v][1:v]ssim=stats_file=/tmp/ssim.log',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Parse SSIM from stderr
            ssim_line = None
            for line in result.stderr.split('\n'):
                if 'SSIM' in line and 'All:' in line:
                    ssim_line = line
                    break
            
            if ssim_line:
                # Extract SSIM values
                parts = ssim_line.split()
                ssim_data = {}
                
                for i, part in enumerate(parts):
                    if 'Y:' in part:
                        try:
                            ssim_data['ssim_y'] = float(part.split(':')[1])
                        except (ValueError, IndexError):
                            continue
                    elif 'U:' in part:
                        try:
                            ssim_data['ssim_u'] = float(part.split(':')[1])
                        except (ValueError, IndexError):
                            continue
                    elif 'V:' in part:
                        try:
                            ssim_data['ssim_v'] = float(part.split(':')[1])
                        except (ValueError, IndexError):
                            continue
                    elif 'All:' in part:
                        try:
                            ssim_data['ssim_all'] = float(part.split(':')[1])
                        except (ValueError, IndexError):
                            continue
                
                return ssim_data
            else:
                return {'error': 'SSIM values not found in output'}
                
        except Exception as e:
            return {'error': f'SSIM calculation failed: {e}'}
    
    def extract_comparison_frames(self, reference_file, encoded_file, num_frames=5):
        """Extract comparison frames for visual inspection"""
        comparison_dir = self.quality_dir / "comparisons" / Path(encoded_file).stem
        comparison_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get video duration
            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(reference_file)]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration = float(json.loads(probe_result.stdout)['format']['duration'])
            
            # Extract frames at different time points
            time_points = np.linspace(duration * 0.1, duration * 0.9, num_frames)
            
            extracted_frames = []
            
            for i, time_point in enumerate(time_points):
                # Extract from reference
                ref_frame = comparison_dir / f"frame_{i:02d}_reference.png"
                ref_cmd = [
                    'ffmpeg', '-ss', str(time_point), '-i', str(reference_file),
                    '-vframes', '1', '-y', str(ref_frame)
                ]
                subprocess.run(ref_cmd, capture_output=True, check=True)
                
                # Extract from encoded
                enc_frame = comparison_dir / f"frame_{i:02d}_encoded.png"
                enc_cmd = [
                    'ffmpeg', '-ss', str(time_point), '-i', str(encoded_file),
                    '-vframes', '1', '-y', str(enc_frame)
                ]
                subprocess.run(enc_cmd, capture_output=True, check=True)
                
                extracted_frames.append({
                    'time': time_point,
                    'reference': str(ref_frame),
                    'encoded': str(enc_frame)
                })
            
            return extracted_frames
            
        except Exception as e:
            return {'error': f'Frame extraction failed: {e}'}
    
    def create_quality_plots(self, benchmark_results):
        """Create visualization plots for benchmark results"""
        if not benchmark_results.get('results'):
            return
        
        # Collect data for plotting
        configs = []
        vmaf_scores = []
        compression_ratios = []
        encoding_times = []
        file_sizes = []
        
        for sample_result in benchmark_results['results']:
            for encoding in sample_result['encodings']:
                if encoding['success'] and 'quality' in encoding and 'vmaf_mean' in encoding['quality']:
                    configs.append(f"{encoding['preset']}\nCQ{encoding['cq']}")
                    vmaf_scores.append(encoding['quality']['vmaf_mean'])
                    compression_ratios.append(encoding['compression_ratio'])
                    encoding_times.append(encoding['encoding_time'])
                    file_sizes.append(encoding['output_size_mb'])
        
        if not configs:
            print("No data available for plotting")
            return
        
        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Nvidia AV1 Encoding Analysis', fontsize=16)
        
        # VMAF vs Compression Ratio
        scatter = ax1.scatter(compression_ratios, vmaf_scores, c=encoding_times, 
                            cmap='viridis', alpha=0.7, s=60)
        ax1.set_xlabel('Compression Ratio')
        ax1.set_ylabel('VMAF Score')
        ax1.set_title('Quality vs Compression (color = encoding time)')
        ax1.axhline(y=95, color='r', linestyle='--', alpha=0.5, label='VMAF 95 threshold')
        ax1.legend()
        plt.colorbar(scatter, ax=ax1, label='Encoding Time (s)')
        
        # VMAF vs Encoding Time
        ax2.scatter(encoding_times, vmaf_scores, alpha=0.7, s=60)
        ax2.set_xlabel('Encoding Time (seconds)')
        ax2.set_ylabel('VMAF Score')
        ax2.set_title('Quality vs Speed')
        ax2.axhline(y=95, color='r', linestyle='--', alpha=0.5)
        
        # File Size vs Compression
        ax3.scatter(file_sizes, compression_ratios, alpha=0.7, s=60)
        ax3.set_xlabel('Output File Size (MB)')
        ax3.set_ylabel('Compression Ratio')
        ax3.set_title('File Size vs Compression')
        
        # Preset Comparison (box plot)
        preset_data = {}
        for i, config in enumerate(configs):
            preset = config.split('\n')[0]
            if preset not in preset_data:
                preset_data[preset] = []
            preset_data[preset].append(vmaf_scores[i])
        
        ax4.boxplot(preset_data.values(), labels=preset_data.keys())
        ax4.set_ylabel('VMAF Score')
        ax4.set_title('VMAF Distribution by Preset')
        ax4.axhline(y=95, color='r', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        # Save plot
        plot_file = self.quality_dir / f"quality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        print(f"📊 Quality analysis plot saved: {plot_file}")
        
        return str(plot_file)
    
    def generate_quality_report(self, benchmark_results):
        """Generate a comprehensive quality report"""
        report_file = self.quality_dir / f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        # Collect and analyze data
        encodings = []
        for sample_result in benchmark_results['results']:
            for encoding in sample_result['encodings']:
                if encoding['success'] and 'quality' in encoding:
                    encoding['sample_name'] = f"{sample_result['source_file']}_{sample_result['scene_type']}"
                    encodings.append(encoding)
        
        if not encodings:
            print("No encoding data available for report")
            return None
        
        # Find optimal configurations
        high_quality = [e for e in encodings if e['quality'].get('vmaf_mean', 0) >= 95]
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Nvidia AV1 Quality Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .metric {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .good {{ background: #d4edda; }}
        .warning {{ background: #fff3cd; }}
        .poor {{ background: #f8d7da; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Nvidia AV1 Encoding Quality Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Summary</h2>
    <div class="metric">
        <strong>Total Encodings:</strong> {len(encodings)}<br>
        <strong>High Quality (VMAF ≥ 95):</strong> {len(high_quality)}<br>
        <strong>Success Rate:</strong> {len(encodings) / len(benchmark_results['results']) * 100:.1f}%
    </div>
"""
        
        if high_quality:
            best_overall = max(high_quality, key=lambda x: x['compression_ratio'])
            html_content += f"""
    <h2>Recommended Configuration</h2>
    <div class="metric good">
        <strong>Configuration:</strong> {best_overall['config']}<br>
        <strong>VMAF Score:</strong> {best_overall['quality'].get('vmaf_mean', 0):.2f}<br>
        <strong>Compression Ratio:</strong> {best_overall['compression_ratio']:.2f}x<br>
        <strong>Encoding Speed:</strong> {best_overall['encoding_time']:.1f}s<br>
        <strong>Sample:</strong> {best_overall['sample_name']}
    </div>
"""
        
        # Detailed results table
        html_content += """
    <h2>Detailed Results</h2>
    <table>
        <tr>
            <th>Sample</th>
            <th>Config</th>
            <th>VMAF</th>
            <th>PSNR</th>
            <th>SSIM</th>
            <th>Compression</th>
            <th>Speed (s)</th>
            <th>Size (MB)</th>
        </tr>
"""
        
        for encoding in sorted(encodings, key=lambda x: x['quality'].get('vmaf_mean', 0), reverse=True):
            vmaf = encoding['quality'].get('vmaf_mean', 0)
            psnr = encoding['quality'].get('psnr_average', 0)
            ssim = encoding['quality'].get('ssim_all', 0)
            
            # Color code based on quality
            row_class = "good" if vmaf >= 95 else "warning" if vmaf >= 90 else "poor"
            
            html_content += f"""
        <tr class="{row_class}">
            <td>{encoding['sample_name']}</td>
            <td>{encoding['config']}</td>
            <td>{vmaf:.2f}</td>
            <td>{psnr:.2f}</td>
            <td>{ssim:.4f}</td>
            <td>{encoding['compression_ratio']:.2f}x</td>
            <td>{encoding['encoding_time']:.1f}</td>
            <td>{encoding['output_size_mb']:.1f}</td>
        </tr>
"""
        
        html_content += """
    </table>
    
    <h2>Quality Thresholds</h2>
    <div class="metric">
        <div class="good">VMAF ≥ 95: Visually transparent quality</div>
        <div class="warning">VMAF 90-95: Good quality, minor artifacts</div>
        <div class="poor">VMAF < 90: Noticeable quality loss</div>
    </div>
</body>
</html>
"""
        
        with open(report_file, 'w') as f:
            f.write(html_content)
        
        print(f"📄 Quality report saved: {report_file}")
        return str(report_file)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Quality Analysis Tool')
    parser.add_argument('--results', '-r', required=True, help='Benchmark results JSON file')
    parser.add_argument('--plot', action='store_true', help='Generate quality plots')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    
    args = parser.parse_args()
    
    if not Path(args.results).exists():
        print(f"❌ Results file not found: {args.results}")
        return 1
    
    with open(args.results, 'r') as f:
        results = json.load(f)
    
    analyzer = QualityAnalyzer()
    
    if args.plot:
        analyzer.create_quality_plots(results)
    
    if args.report:
        analyzer.generate_quality_report(results)
    
    return 0

if __name__ == "__main__":
    exit(main())
