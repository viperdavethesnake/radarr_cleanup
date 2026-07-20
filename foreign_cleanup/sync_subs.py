#!/usr/bin/env python3
"""
Sync OpenSubtitles SRTs to a film's audio, per the pipeline rules.

Full track: ffsubsync against the MKV's audio. A framerate scale factor other
than 1.000 aborts the film — that signals a different cut, not an offset, and
muxing it would produce plausible-looking drift.

Forced track (optional): NEVER ffsubsync'd independently. Sparse tracks (title
cards over silence) give the aligner almost nothing to lock onto and it returns
a confident wrong answer — measured on All Quiet (2022): scale 1.043, 0/92 text
matches vs the trusted full track. The full track's measured offset is applied
to the forced track flat instead.
"""

import os, re, sys, argparse, subprocess, datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, '.venv', 'lib'))

import srt  # noqa: E402

SCALE_TOLERANCE = 0.001

# Scale factors accepted without question: no correction, and the NTSC
# 23.976⇄24.000 pair (verified legitimate on A Private Life 2025 — sub timed
# against a 23.976 AMZN release, file measured at 24.000). PAL ratios (~1.043)
# stay hard-blocked: that pattern produced a confident-but-wrong alignment on
# the All Quiet (2022) forced track.
ACCEPTED_SCALES = (1.0, 24 / 23.976, 23.976 / 24)


def run_ffsubsync(mkv, srt_in, srt_out):
    r = subprocess.run(['ffsubsync', mkv, '-i', srt_in, '-o', srt_out],
                       capture_output=True, text=True, timeout=1800)
    txt = (r.stdout or '') + (r.stderr or '')
    m_off = re.search(r'offset seconds:\s*(-?[\d.]+)', txt)
    m_sc = re.search(r'framerate scale factor:\s*([\d.]+)', txt)
    if r.returncode != 0 or not m_off or not m_sc:
        raise RuntimeError(f'ffsubsync failed (exit {r.returncode}): {txt[-400:]}')
    return float(m_off.group(1)), float(m_sc.group(1))


def shift_srt(srt_in, srt_out, offset_seconds):
    cues = list(srt.parse(open(srt_in, encoding='utf-8', errors='replace').read()))
    delta = datetime.timedelta(seconds=offset_seconds)
    for c in cues:
        c.start += delta
        c.end += delta
    cues = [c for c in cues if c.start.total_seconds() >= 0]
    with open(srt_out, 'w', encoding='utf-8') as f:
        f.write(srt.compose(cues))
    return cues


def runtime_seconds(mkv):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', mkv],
                       capture_output=True, text=True, timeout=120)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mkv', help='Source MKV (audio reference)')
    ap.add_argument('--full', required=True, help='Full-dialogue SRT (raw, from OpenSubtitles)')
    ap.add_argument('--full-out', required=True, help='Output path for synced full SRT')
    ap.add_argument('--forced', help='Forced SRT (raw) — gets the full track offset applied flat')
    ap.add_argument('--forced-out', help='Output path for shifted forced SRT')
    args = ap.parse_args()

    if args.forced and not args.forced_out:
        ap.error('--forced requires --forced-out')

    offset, scale = run_ffsubsync(args.mkv, args.full, args.full_out)
    print(f'full   : offset={offset:+.3f}s scale={scale:.3f}')

    if not any(abs(scale - s) <= SCALE_TOLERANCE for s in ACCEPTED_SCALES):
        for p in (args.full_out,):
            if os.path.exists(p):
                os.remove(p)
        print(f'ABORT: framerate scale {scale:.3f} != 1.000 — different cut, '
              f'find another subtitle source for this film')
        return 2

    dur = runtime_seconds(args.mkv)
    cues = list(srt.parse(open(args.full_out, encoding='utf-8', errors='replace').read()))
    last = cues[-1].end.total_seconds()
    print(f'full   : {len(cues)} cues, last ends {last/60:.2f}min of {dur/60:.2f}min '
          f'{"OK" if last <= dur else "** OVERRUNS RUNTIME **"}')
    if last > dur:
        return 2

    if args.forced:
        fcues = shift_srt(args.forced, args.forced_out, offset)
        flast = fcues[-1].end.total_seconds()
        print(f'forced : {len(fcues)} cues shifted {offset:+.3f}s flat, '
              f'last ends {flast/60:.2f}min '
              f'{"OK" if flast <= dur else "** OVERRUNS RUNTIME **"}')
        if flast > dur:
            return 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
