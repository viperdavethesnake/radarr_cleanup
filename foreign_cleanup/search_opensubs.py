#!/usr/bin/env python3
"""
Search OpenSubtitles for English subtitles by IMDb ID. Read-only: searches and
reports, downloads nothing.
"""

import os, sys, json, time, argparse
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, '.env'))

API = 'https://api.opensubtitles.com/api/v1'
KEY = os.getenv('OPENSUB_API_KEY')
UA = 'radarr_cleanup-foreign/1.0'


def search(imdb_id, lang='en'):
    numeric = imdb_id.lstrip('t')
    r = requests.get(f'{API}/subtitles',
                     params={'imdb_id': numeric, 'languages': lang,
                             'order_by': 'download_count', 'order_direction': 'desc'},
                     headers={'Api-Key': KEY, 'User-Agent': UA, 'Accept': 'application/json'},
                     timeout=30)
    r.raise_for_status()
    return r.json()


def summarize(entry):
    a = entry.get('attributes', {})
    files = a.get('files') or [{}]
    feat = a.get('feature_details') or {}
    return {
        'id': entry.get('id'),
        'file_id': files[0].get('file_id'),
        'release': a.get('release'),
        'downloads': a.get('download_count'),
        'rating': a.get('ratings'),
        'votes': a.get('votes'),
        'hearing_impaired': a.get('hearing_impaired'),
        'foreign_parts_only': a.get('foreign_parts_only'),
        'machine_translated': a.get('machine_translated'),
        'ai_translated': a.get('ai_translated'),
        'trusted': (a.get('uploader') or {}).get('rank'),
        'fps': a.get('fps'),
        'upload_date': (a.get('upload_date') or '')[:10],
        'format': files[0].get('file_name', '').split('.')[-1] if files[0].get('file_name') else None,
        'file_name': files[0].get('file_name'),
        'year': feat.get('year'),
        'title': feat.get('title'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('imdb', nargs='+', help='IMDb IDs (tt####### or numeric)')
    ap.add_argument('--lang', default='en')
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--json', help='Write full results to JSON')
    args = ap.parse_args()

    if not KEY:
        print('❌ OPENSUB_API_KEY not set in .env')
        return 1

    out = {}
    for imdb in args.imdb:
        try:
            data = search(imdb, args.lang)
        except Exception as e:
            print(f'❌ {imdb}: {e}')
            if getattr(e, 'response', None) is not None:
                print(f'   {e.response.text[:300]}')
            continue

        rows = [summarize(x) for x in data.get('data', [])]
        out[imdb] = rows
        print(f'\n=== {imdb} — {data.get("total_count", 0)} English result(s)')
        if rows:
            print(f'    {rows[0].get("title")} ({rows[0].get("year")})')
        for r in rows[:args.top]:
            tags = []
            if r['hearing_impaired']:
                tags.append('HI')
            if r['foreign_parts_only']:
                tags.append('FORCED')
            if r['machine_translated']:
                tags.append('MACHINE')
            if r['ai_translated']:
                tags.append('AI')
            print(f"  dl={r['downloads'] or 0:<7} rating={r['rating'] or 0:<4} "
                  f"fps={r['fps'] or '-':<7} {r['upload_date']:<11} "
                  f"{','.join(tags) or '-':<16} {(r['release'] or '')[:60]}")
        time.sleep(0.5)

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f'\n📄 {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
