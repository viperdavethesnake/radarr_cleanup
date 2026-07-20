#!/usr/bin/env python3
"""
Download subtitle files from OpenSubtitles by file_id and report quota.

OpenSubtitles meters downloads separately from searches, so this reports
`remaining` after every call — quota exhaustion is the usual failure here,
not a network error.
"""

import os, sys, json, argparse
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, '.env'))

API = 'https://api.opensubtitles.com/api/v1'
KEY = os.getenv('OPENSUB_API_KEY')
UA = 'radarr_cleanup-foreign/1.0'


def headers():
    return {'Api-Key': KEY, 'User-Agent': UA,
            'Accept': 'application/json', 'Content-Type': 'application/json'}


def fetch(file_id, dest):
    r = requests.post(f'{API}/download', headers=headers(),
                      data=json.dumps({'file_id': int(file_id)}), timeout=30)
    if r.status_code != 200:
        return None, f'HTTP {r.status_code}: {r.text[:200]}'
    info = r.json()
    link = info.get('link')
    if not link:
        return None, f'no link in response: {json.dumps(info)[:200]}'

    sub = requests.get(link, timeout=60)
    sub.raise_for_status()
    os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
    with open(dest, 'wb') as f:
        f.write(sub.content)
    return info, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pairs', nargs='+', help='file_id:output_path')
    args = ap.parse_args()

    if not KEY:
        print('❌ OPENSUB_API_KEY not set')
        return 1

    for pair in args.pairs:
        file_id, dest = pair.split(':', 1)
        info, err = fetch(file_id, dest)
        if err:
            print(f'❌ {file_id}: {err}')
            continue
        size = os.path.getsize(dest)
        print(f'✅ {file_id} → {dest} ({size:,} bytes) '
              f'| used={info.get("requests")} remaining={info.get("remaining")} '
              f'reset={info.get("reset_time")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
