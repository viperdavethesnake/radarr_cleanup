# Foreign Film Pipeline

The standing process for non-English-original films. The English pipeline
(`movie_cleanup/`) is never modified; its library functions are imported and
its conventions copied where they fit. The difference is control: the English
pipeline decides for itself, this one puts every decision in front of David.

## Rules (fixed)

1. Original-language audio, highest quality in the source — **default**
2. English text subtitle — **default**
3. English dub, highest quality, secondary — if one exists
4. Everything else dropped: other audio, other-language subs, PGS, attachments
5. Subtitles: OpenSubtitles or already-present text tracks only.
   **No OCR, no Whisper — not approved.** If no clean SRT can be had, keep the
   source PGS and move on.
6. Forced subtitle tracks inherit the full track's measured offset — never
   independently ffsubsync'd (sparse tracks make it produce confident garbage).
7. Chapters kept if clean (sane timestamps, no junk entries).
8. Per-film decisions. Tools report state; David decides. No severity labels,
   no auto-routing.
9. Working area is `/storage/media/servarr` only. Output to `cleaned/`.
   The Jellyfin library and Radarr are never touched.
10. Sources are deleted only on David's explicit instruction, after outputs
    verify and he has had the chance to spot-check.

## Stage flow (per film)

```
foreign/<Film>/
   │ 1. inspect        read-only: tracks, TMDB identity, chapters, attachments
   │ 2. report         findings to David, per film
   │ 3. decide         David picks tracks / sub route; captured in spec JSON
   │ 4. subtitles      OpenSubtitles fetch → ffsubsync full track →
   │                   forced track gets the full track's offset applied flat
   │ 5. dry-run        spec validated against the actual file; abort on drift
   │ 6. remux          one mkvmerge; full clean (below)
   │ 7. metadata       regenerate NFO + artwork from TMDB; inject clean tags
   │ 8. verify         layout, runtime, text-only subs, chapters, sidecars
   │ 9. spot-check     3 frames (5min / mid / end-5min) rendered for David
   ▼
cleaned/<Film>/        source stays in foreign/ until David says delete
```

Steps 1–2 and 4–9 are automated; 3 and the final deletion are David's.

## What "full clean" means at remux (mirrors the English pipeline)

- Only spec'd tracks survive; every track's language/default/forced flag set
  explicitly — nothing inherited
- `--no-attachments` always (also sidesteps the mkvpropedit `=<uid>` gotcha)
- Video language forced to `und`
- Source global tags and per-track statistics tags do not carry through
  (mkvmerge remux drops them; verified on the first five outputs)
- Container title left empty
- Fresh `tags.xml` from TMDB injected via `mkvpropedit --tags all:` —
  embedded IMDb/TMDB tags are the authoritative identity (repo convention)
- `movie.nfo`, `poster.jpg`, `fanart.jpg` **regenerated from TMDB**, not
  copied from the source folder
- Output filename computed from the actual selected tracks:
  `Title_(Year)_[<height>p_<vcodec>_<acodec>].mkv` via the same logic as
  `enhanced_file_name()` — never hand-typed

## Reused from `movie_cleanup/batch_cleaner.py` (imported, not copied)

`fetch_tmdb_metadata`, `write_nfo`, `write_tags_xml`, `set_tags_in_mkv`,
`download_image`, `find_imdbid`, `clean_folder_name` — plus the
codec-shortname/filename logic mirrored from `mkv_remux_cleanroom.py`.

## Conventions carried over

- Dry-run by default; `--run` to execute
- Concurrency 3–4 workers max (storage-bound pool, co-resident Jellyfin/
  Frigate/Ollama); timeout 3600s per film; a timeout means pool trouble —
  investigate, don't retry bigger
- Logs to `logs/`, timestamped, console + file
- Errors accumulate and report at the end; graceful SIGINT/SIGTERM

## Tooling

| Script | Role | State |
|---|---|---|
| `inspect_foreign.py` | read-only track/identity report | needs severity labels stripped → observations only |
| `search_opensubs.py` | OpenSubtitles search by IMDb id | done |
| `fetch_opensubs.py` | download by file_id, quota report | done |
| `remux_foreign.py` | spec-driven remux + validation | needs: NFO/artwork regeneration, computed filename |
| `scan_library_languages.py` | original-language check for a staging dir | done |
| spec JSONs | one per batch, captures David's decisions | written per batch |

## Build list (before processing the next seven)

1. `remux_foreign.py`: regenerate NFO/poster/fanart from TMDB instead of
   copying source sidecars; compute output filename from selected tracks.
2. `inspect_foreign.py`: strip error/warn framing and recommendation text;
   facts only.
3. Encode the forced-track offset-inheritance rule in the sync step so it is
   process, not memory.

## Queue

Batch 3 (2026-07-19, spec_batch3.json) done: Das_Boot (de), Life_Is_Beautiful
(it), Crouching_Tiger,_Hidden_Dragon (zh), Cinema_Paradiso (it), The_Leopard
(it) — remuxed, verified, container titles cleared. As of 2026-07-20 the
queue is empty: all cleaned outputs are in the library (batch 1/2 in
`movies2`, batch 3 + Ip_Man_4 in `movies`), all sources deleted by David,
`foreign/` and `cleaned/` are empty. A_Private_Life was discarded entirely
(bad source copy).

Skipped on David's call (2026-07-19): A_Fistful_of_Dollars and
The_Good,_the_Bad_and_the_Ugly — treated as English-canonical spaghetti
westerns, left untouched in `movies2`. Synced SRTs for both remain in
`subs/` unused.

movies2 scan 2026-07-19: all 144 identified films resolved; no other
non-English originals remain. Known leftover: The_Traitor's copy in
`movies2` still carries the source container title (batch-2 leak, fixed in
the tool since).
