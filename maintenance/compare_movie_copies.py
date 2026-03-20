#!/usr/bin/env python3
"""
Compare two movie libraries (read-only) and print results to screen.

PathA (new copies):  /storage/media/servarr/cleaned
PathB (older copies): /storage/media/movies

Outputs:
1) Movies present in PathA but not in PathB
2) Movies present in both, with side-by-side video/audio details for judgement

Requires external tools in PATH:
- ffprobe (from FFmpeg)
- mkvmerge (from MKVToolNix)
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET


# NEW = newly downloaded / newly processed copies (candidate replacements)
DEFAULT_NEW_PATH = "/storage/media/servarr/cleaned"

# EXISTING = your current library (the stuff you already have)
DEFAULT_EXISTING_PATH = "/storage/media/movies"

SIDE_NEW = "NEW"
SIDE_EXISTING = "EXISTING"


def _which_ok(bin_name: str) -> bool:
    from shutil import which

    return which(bin_name) is not None


def _run_json(cmd: List[str], timeout: int) -> Dict[str, Any]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    try:
        return json.loads(p.stdout)
    except Exception as e:
        raise RuntimeError(f"Invalid JSON from: {' '.join(cmd)}: {e}") from e


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def _norm_title(s: str) -> str:
    s = s.replace("_", " ").strip().lower()
    s = re.sub(r"\[[^\]]+\]", " ", s)  # drop [2160p_HEVC_EAC3] style chunks
    s = re.sub(r"\([^)]*\)", " ", s)  # drop (...) chunks (often year)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_imdb_any(text: str) -> Optional[str]:
    m = re.search(r"(tt\d{6,9})", text, re.IGNORECASE)
    return m.group(1).lower() if m else None


def _folder_candidates(root: str) -> List[str]:
    try:
        entries = os.listdir(root)
    except FileNotFoundError:
        return []
    out: List[str] = []
    for name in entries:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            out.append(p)
    out.sort()
    return out


def _pick_main_mkv(folder: str) -> Tuple[Optional[str], List[str]]:
    mkvs = [f for f in os.listdir(folder) if f.lower().endswith(".mkv")]
    if not mkvs:
        return None, []
    if len(mkvs) == 1:
        return os.path.join(folder, mkvs[0]), mkvs
    # Per workflow requirement: ignore folders with multiple MKVs (ambiguous).
    return None, mkvs


def _read_text_if_exists(path: str, max_bytes: int = 2_000_000) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return None


def _parse_movie_nfo(folder: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (imdb_id, title, year)
    """
    nfo = os.path.join(folder, "movie.nfo")
    txt = _read_text_if_exists(nfo)
    if not txt:
        # Try any .nfo
        for f in os.listdir(folder):
            if f.lower().endswith(".nfo"):
                txt = _read_text_if_exists(os.path.join(folder, f))
                if txt:
                    break
    if not txt:
        return None, None, None

    imdb: Optional[str] = None
    title: Optional[str] = None
    year: Optional[str] = None

    # XML parse first (best effort)
    try:
        root = ET.fromstring(txt)
        imdb_raw = root.findtext("imdbid") or root.findtext("id")
        if imdb_raw:
            imdb = _extract_imdb_any(imdb_raw)
        title_raw = root.findtext("title")
        if title_raw:
            title = title_raw.strip()
        year_raw = root.findtext("year")
        if year_raw and re.fullmatch(r"\d{4}", year_raw.strip()):
            year = year_raw.strip()
    except Exception:
        pass

    # Regex fallback for imdb + year/title
    if not imdb:
        imdb = _extract_imdb_any(txt)
    if not year:
        m = re.search(r"<year>\s*(\d{4})\s*</year>", txt, re.IGNORECASE)
        if m:
            year = m.group(1)
    if not title:
        m = re.search(r"<title>\s*(.*?)\s*</title>", txt, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

    return imdb, title, year


def _infer_title_year_from_folder(folder: str) -> Tuple[Optional[str], Optional[str]]:
    base = os.path.basename(folder)
    m = re.search(r"(.+?)\s*\(?(\d{4})\)?", base)
    if not m:
        return None, None
    raw_title = m.group(1)
    raw_year = m.group(2)
    title = raw_title.replace("_", " ").strip()
    year = raw_year if re.fullmatch(r"\d{4}", raw_year) else None
    return title or None, year


def _make_key(imdb: Optional[str], title: Optional[str], year: Optional[str], folder: str) -> Tuple[str, str]:
    if imdb:
        return "imdb", imdb.lower()
    if title and year:
        return "titleyear", f"{_norm_title(title)}::{year}"
    # Last resort: normalized folder name (more collisions; flagged later)
    return "folder", _norm_title(os.path.basename(folder))


def _human_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024.0 or u == units[-1]:
            return f"{f:.1f}{u}" if u != "B" else f"{int(f)}B"
        f /= 1024.0
    return f"{int(n)}B"


def _human_bps(bps: Optional[int]) -> str:
    if bps is None:
        return "?"
    if bps >= 1_000_000:
        return f"{bps/1_000_000:.2f}Mb/s"
    if bps >= 1_000:
        return f"{bps/1_000:.0f}kb/s"
    return f"{bps}b/s"


def _parse_ratio(r: Any) -> Optional[float]:
    # ffprobe often returns strings like "24000/1001"
    if r is None:
        return None
    if isinstance(r, (int, float)):
        return float(r)
    if isinstance(r, str):
        if "/" in r:
            a, b = r.split("/", 1)
            fa = _safe_float(a)
            fb = _safe_float(b)
            if fa is not None and fb not in (None, 0.0):
                return fa / fb
        return _safe_float(r)
    return None


def _codec_rank(codec: str) -> int:
    c = (codec or "").lower()
    # Lower is better.
    if "truehd" in c:
        return 0
    if "dts" in c and ("hd" in c or "ma" in c):
        return 1
    if "dts" in c:
        return 2
    if "eac3" in c or "ec-3" in c:
        return 3
    if "ac3" in c:
        return 4
    if "flac" in c:
        return 5
    if "aac" in c:
        return 6
    if "mp3" in c:
        return 7
    return 99


def _is_english(lang: Optional[str]) -> bool:
    if not lang:
        return True  # treat missing as acceptable
    lang = lang.lower()
    return lang in {"en", "eng", "en-us", "en-gb", "und", ""}


@dataclass(frozen=True)
class TrackSummary:
    idx: int
    lang: str
    codec: str
    codec_long: str
    channels: str
    sample_rate_hz: Optional[int]
    bitrate_bps: Optional[int]
    title: str
    default: bool
    atmos: bool


@dataclass(frozen=True)
class MediaSummary:
    mkv_path: str
    size_bytes: Optional[int]
    duration_s: Optional[float]
    # Video
    v_codec: str
    v_profile: str
    v_level: str
    v_res: str
    v_fps: Optional[float]
    v_bit_depth: Optional[int]
    v_pix_fmt: str
    v_bitrate_bps: Optional[int]
    v_hdr_format: str  # DV / HDR10+ / HDR10 / HLG / SDR / ?
    v_color_primaries: str
    v_color_transfer: str
    v_colorspace: str
    v_mastering: str
    v_maxcll: Optional[int]
    v_maxfall: Optional[int]
    # Audio
    audio_tracks: Tuple[TrackSummary, ...]
    best_audio_idx: Optional[int]


def _ffprobe(mkv_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        mkv_path,
    ]
    return _run_json(cmd, timeout=60)


def _mkvmerge_json(mkv_path: str) -> Dict[str, Any]:
    cmd = ["mkvmerge", "-J", mkv_path]
    return _run_json(cmd, timeout=60)


def _bit_depth_from_pix_fmt(pix_fmt: str) -> Optional[int]:
    # Common: yuv420p10le, yuv444p12le, etc.
    m = re.search(r"p(\d{2})", pix_fmt or "")
    if m:
        return int(m.group(1))
    return None


def _pick_default_stream(streams: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not streams:
        return None
    streams = list(streams)
    streams.sort(key=lambda s: 0 if (s.get("disposition") or {}).get("default") == 1 else 1)
    return streams[0]


def _detect_hdr_format(v: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Returns (hdr_format, mastering_sd, cll_sd)
    """
    side = v.get("side_data_list") or []
    side_types = [str(sd.get("side_data_type") or "") for sd in side]
    side_types_l = [t.lower() for t in side_types]

    mastering = None
    cll = None
    dovi_seen = False
    for sd in side:
        t = str(sd.get("side_data_type") or "")
        tl = t.lower()
        if "mastering display metadata" in tl:
            mastering = sd
        if "content light level" in tl:
            cll = sd
        # ffprobe typically reports Dolby Vision as "DOVI configuration record"
        if "dovi configuration record" in tl or tl.strip() == "dovi":
            dovi_seen = True

    # Dolby Vision (strict)
    if dovi_seen:
        return "DV", mastering, cll

    # HDR10+
    # Common ffprobe: "HDR10+ Metadata" or "SMPTE ST 2094-40 (HDR10+)"
    if any("hdr10+" in tl or "2094-40" in tl or "hdr10+ metadata" in tl for tl in side_types_l):
        return "HDR10+", mastering, cll

    tr = (v.get("color_transfer") or "").lower()
    cp = (v.get("color_primaries") or "").lower()

    if tr == "arib-std-b67":
        return "HLG", mastering, cll

    # HDR10 (PQ + BT.2020 primaries)
    if tr == "smpte2084" and cp.startswith("bt2020"):
        return "HDR10", mastering, cll

    # If we have mastering metadata but no clear transfer/primaries, treat as unknown HDR-ish.
    if mastering is not None or cll is not None:
        return "UNKNOWN", mastering, cll

    return "SDR", mastering, cll


def _fmt_mastering(mastering_sd: Optional[Dict[str, Any]]) -> str:
    if not mastering_sd:
        return ""
    # ffprobe field names vary; print the most helpful ones if present
    max_lum = mastering_sd.get("max_luminance")
    min_lum = mastering_sd.get("min_luminance")
    parts = []
    if max_lum is not None:
        parts.append(f"maxLum={max_lum}")
    if min_lum is not None:
        parts.append(f"minLum={min_lum}")
    return " ".join(parts)


def _extract_maxcll_maxfall(cll_sd: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
    if not cll_sd:
        return None, None
    maxcll = _safe_int(cll_sd.get("max_content"))
    maxfall = _safe_int(cll_sd.get("max_average"))
    return maxcll, maxfall


def _collect_audio_tracks(ffp: Dict[str, Any], mkv: Dict[str, Any]) -> List[TrackSummary]:
    # Map mkvmerge track id -> properties (language, track_name, flags)
    mkv_tracks = mkv.get("tracks") or []
    mkv_audio = [t for t in mkv_tracks if t.get("type") == "audio"]
    by_id: Dict[int, Dict[str, Any]] = {}
    for t in mkv_audio:
        try:
            tid = int(t.get("id"))
        except Exception:
            continue
        by_id[tid] = t.get("properties") or {}

    streams = ffp.get("streams") or []
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    out: List[TrackSummary] = []
    for idx, s in enumerate(audios):
        tags = s.get("tags") or {}
        lang = (tags.get("language") or "").lower()
        codec = (s.get("codec_name") or "").lower() or "?"
        codec_long = (s.get("codec_long_name") or "").strip()
        ch = s.get("channels")
        layout = s.get("channel_layout")
        ch_s = "?"
        if ch is not None:
            ch_s = str(ch)
            if layout:
                ch_s = f"{ch_s}ch({layout})"

        sample_rate_hz = _safe_int(s.get("sample_rate"))
        bitrate_bps = _safe_int(s.get("bit_rate"))

        # mkvmerge track ids do not always match ffprobe stream indices, but often do in simple files.
        # We'll attempt a best-effort mapping: use stream index as track id if present.
        title = ""
        default = False
        sid = _safe_int(s.get("index"))
        props = by_id.get(sid, {}) if sid is not None else {}
        title = (props.get("track_name") or "").strip()
        default = bool(props.get("default_track")) or bool((s.get("disposition") or {}).get("default") == 1)

        # fallback: title from ffprobe tags
        if not title:
            title = (tags.get("title") or "").strip()

        # Atmos detection (best effort from codec + title string)
        title_l = title.lower()
        atmos = False
        if "atmos" in title_l:
            atmos = True
        if codec in {"truehd", "eac3", "ec-3"} and ("joc" in title_l or "dolby atmos" in title_l):
            atmos = True

        out.append(
            TrackSummary(
                idx=idx,
                lang=lang or "und",
                codec=codec,
                codec_long=codec_long,
                channels=ch_s,
                sample_rate_hz=sample_rate_hz,
                bitrate_bps=bitrate_bps,
                title=title,
                default=default,
                atmos=atmos,
            )
        )
    return out


def _pick_best_audio(tracks: List[TrackSummary]) -> Optional[int]:
    if not tracks:
        return None

    def score(t: TrackSummary) -> Tuple[int, int, int]:
        # (language penalty, codec rank, non-default penalty)
        lang_pen = 0 if _is_english(t.lang) else 1
        cr = _codec_rank(t.codec)
        def_pen = 0 if t.default else 1
        return (lang_pen, cr, def_pen)

    best = min(tracks, key=score)
    return best.idx


def summarize_media(mkv_path: str) -> MediaSummary:
    try:
        size = os.path.getsize(mkv_path)
    except Exception:
        size = None

    ffp = _ffprobe(mkv_path)
    mkv = _mkvmerge_json(mkv_path)

    dur_s: Optional[float] = None
    try:
        dur_raw = (ffp.get("format") or {}).get("duration")
        dur_s = float(dur_raw) if dur_raw is not None else None
    except Exception:
        dur_s = None

    streams = ffp.get("streams") or []
    vids = [s for s in streams if s.get("codec_type") == "video"]
    v = _pick_default_stream(vids) or {}

    v_codec = (v.get("codec_name") or "?").lower()
    v_profile = str(v.get("profile") or "").strip()
    v_level = str(v.get("level") or "").strip()
    w = v.get("width")
    h = v.get("height")
    v_res = f"{w}x{h}" if w and h else "?"
    v_pix_fmt = str(v.get("pix_fmt") or "").strip()
    v_bit_depth = _bit_depth_from_pix_fmt(v_pix_fmt)
    v_bitrate_bps = _safe_int(v.get("bit_rate"))

    # Frame rate: prefer avg_frame_rate; fallback r_frame_rate
    v_fps = _parse_ratio(v.get("avg_frame_rate")) or _parse_ratio(v.get("r_frame_rate"))

    v_color_primaries = str(v.get("color_primaries") or "").strip()
    v_color_transfer = str(v.get("color_transfer") or "").strip()
    v_colorspace = str(v.get("colorspace") or "").strip()

    v_hdr_format, mastering_sd, cll_sd = _detect_hdr_format(v)
    v_mastering = _fmt_mastering(mastering_sd)
    v_maxcll, v_maxfall = _extract_maxcll_maxfall(cll_sd)

    audio_tracks = _collect_audio_tracks(ffp, mkv)
    best_audio_idx = _pick_best_audio(audio_tracks)

    return MediaSummary(
        mkv_path=mkv_path,
        size_bytes=size,
        duration_s=dur_s,
        v_codec=v_codec,
        v_profile=v_profile,
        v_level=v_level,
        v_res=v_res,
        v_fps=v_fps,
        v_bit_depth=v_bit_depth,
        v_pix_fmt=v_pix_fmt,
        v_bitrate_bps=v_bitrate_bps,
        v_hdr_format=v_hdr_format,
        v_color_primaries=v_color_primaries,
        v_color_transfer=v_color_transfer,
        v_colorspace=v_colorspace,
        v_mastering=v_mastering,
        v_maxcll=v_maxcll,
        v_maxfall=v_maxfall,
        audio_tracks=tuple(audio_tracks),
        best_audio_idx=best_audio_idx,
    )


@dataclass
class MovieEntry:
    folder: str
    mkv_path: Optional[str]
    mkv_names: List[str]
    imdb: Optional[str]
    title: Optional[str]
    year: Optional[str]
    key_type: str
    key_value: str
    warnings: List[str]

    @property
    def key(self) -> Tuple[str, str]:
        return (self.key_type, self.key_value)


def index_library(root: str, side_label: str) -> Tuple[Dict[Tuple[str, str], List[MovieEntry]], List[str]]:
    problems: List[str] = []
    by_key: Dict[Tuple[str, str], List[MovieEntry]] = {}

    folders = _folder_candidates(root)
    if not folders:
        problems.append(f"[WARN] {side_label}: No folders found under: {root}")

    for folder in folders:
        warnings: List[str] = []
        mkv_path, mkv_names = _pick_main_mkv(folder)
        if len(mkv_names) > 1:
            # Explicitly skip ambiguous folders with multiple MKVs
            problems.append(
                f"[SKIP] {side_label}: multiple MKVs in folder '{os.path.basename(folder)}' ({len(mkv_names)} files)"
            )
            continue
        if not mkv_path:
            warnings.append("no_mkv")

        imdb, title, year = _parse_movie_nfo(folder)
        if not imdb:
            # Try from folder/mkv name
            imdb = _extract_imdb_any(os.path.basename(folder))
            if not imdb and mkv_path:
                imdb = _extract_imdb_any(os.path.basename(mkv_path))

        if not title or not year:
            t2, y2 = _infer_title_year_from_folder(folder)
            title = title or t2
            year = year or y2

        key_type, key_value = _make_key(imdb, title, year, folder)
        if key_type != "imdb":
            warnings.append(f"weak_key({key_type})")

        ent = MovieEntry(
            folder=folder,
            mkv_path=mkv_path,
            mkv_names=mkv_names,
            imdb=imdb,
            title=title,
            year=year,
            key_type=key_type,
            key_value=key_value,
            warnings=warnings,
        )

        by_key.setdefault(ent.key, []).append(ent)

    return by_key, problems


def _fmt_identity(e: MovieEntry) -> str:
    # Prefer human-friendly display if we have it
    if e.title and e.year:
        return f"{e.title} ({e.year})"
    if e.imdb:
        return e.imdb
    return os.path.basename(e.folder)


def _fmt_audio_tracks(ms: MediaSummary) -> str:
    if not ms.audio_tracks:
        return "audio: (none)"

    # Print best track first (then count of others)
    best: Optional[TrackSummary] = None
    for t in ms.audio_tracks:
        if ms.best_audio_idx == t.idx:
            best = t
            break
    if best is None:
        best = ms.audio_tracks[0]

    atmos = " Atmos" if best.atmos else ""
    title = f" title='{best.title}'" if best.title else ""
    sr = f" sr={best.sample_rate_hz}Hz" if best.sample_rate_hz else ""
    br = f" br={_human_bps(best.bitrate_bps)}" if best.bitrate_bps else ""
    d = " default" if best.default else ""

    others = len(ms.audio_tracks) - 1
    other_s = f" (+{others} other audio tracks)" if others > 0 else ""
    return f"audio(best): a{best.idx}:{best.lang}:{best.codec}{atmos}:{best.channels}{d}{sr}{br}{title}{other_s}"


def _fmt_video(ms: MediaSummary) -> str:
    fps = f"{ms.v_fps:.3f}fps" if ms.v_fps is not None else "?fps"
    bd = f"{ms.v_bit_depth}-bit" if ms.v_bit_depth else "?bit"
    prof = f" prof={ms.v_profile}" if ms.v_profile else ""
    lvl = f" lvl={ms.v_level}" if ms.v_level else ""
    br = f" br={_human_bps(ms.v_bitrate_bps)}" if ms.v_bitrate_bps else " br=?"
    pix = f" pix={ms.v_pix_fmt}" if ms.v_pix_fmt else ""
    return f"video: {ms.v_codec} {ms.v_res} {bd} {fps}{br}{prof}{lvl}{pix}"


def _fmt_hdr(ms: MediaSummary) -> str:
    parts = [f"hdr: {ms.v_hdr_format}"]
    if ms.v_color_primaries:
        parts.append(f"prim={ms.v_color_primaries}")
    if ms.v_color_transfer:
        parts.append(f"trc={ms.v_color_transfer}")
    if ms.v_colorspace:
        parts.append(f"cs={ms.v_colorspace}")
    if ms.v_maxcll is not None or ms.v_maxfall is not None:
        parts.append(f"MaxCLL={ms.v_maxcll if ms.v_maxcll is not None else '?'}")
        parts.append(f"MaxFALL={ms.v_maxfall if ms.v_maxfall is not None else '?'}")
    if ms.v_mastering:
        parts.append(f"mastering({ms.v_mastering})")
    return " ".join(parts)


def _parse_res_pixels(res: str) -> int:
    m = re.match(r"(\d+)x(\d+)", res or "")
    if not m:
        return 0
    return int(m.group(1)) * int(m.group(2))


def _hdr_rank(h: str) -> int:
    # Higher is better
    h = (h or "").upper()
    order = {
        "DV": 5,
        "HDR10+": 4,
        "HDR10": 3,
        "HLG": 2,
        "HDR(PQ)": 2,
        "WCG(BT2020)": 1,
        "SDR": 0,
    }
    return order.get(h, -1)


def _vcodec_rank(c: str) -> int:
    # Higher is better
    c = (c or "").lower()
    if c == "av1":
        return 4
    if c in {"hevc", "h265", "h.265"}:
        return 3
    if c in {"h264", "avc", "h.264"}:
        return 2
    if c in {"mpeg2video", "mpeg2"}:
        return 1
    return 0


def _audio_channels_count(chs: str) -> int:
    # "8ch(7.1)" -> 8 ; "6ch(...)" -> 6
    m = re.match(r"(\d+)ch", chs or "")
    if m:
        return int(m.group(1))
    # sometimes it is plain "2" etc.
    return _safe_int(chs) or 0


def _best_audio(ms: MediaSummary) -> Optional[TrackSummary]:
    if not ms.audio_tracks:
        return None
    if ms.best_audio_idx is None:
        return ms.audio_tracks[0]
    for t in ms.audio_tracks:
        if t.idx == ms.best_audio_idx:
            return t
    return ms.audio_tracks[0]


def _video_bitrate_effective_bps(ms: MediaSummary) -> Tuple[Optional[int], bool]:
    """
    Returns (bps, used_proxy)
    - Prefer stream bitrate if present
    - Else proxy with file_size / duration (very rough, but better than nothing)
    """
    if ms.v_bitrate_bps and ms.v_bitrate_bps > 0:
        return ms.v_bitrate_bps, False
    if ms.size_bytes and ms.duration_s and ms.duration_s > 0:
        # container+audio included; still useful for relative comparisons when both are similar
        return int((ms.size_bytes * 8) / ms.duration_s), True
    return None, True


def recommend_keep(new: MediaSummary, existing: MediaSummary) -> Tuple[str, str, List[str], str]:
    """
    Returns (keep, basis, reasons, confidence)
    keep: "NEW" | "EXISTING" | "TIE"
    basis: "video" | "audio" | "tie"
    confidence: "high" | "medium" | "low"
    """
    reasons: List[str] = []
    confidence = "high"

    # 1) VIDEO-FIRST comparison (dominant)
    new_px = _parse_res_pixels(new.v_res)
    ex_px = _parse_res_pixels(existing.v_res)
    if new_px != ex_px:
        keep = SIDE_NEW if new_px > ex_px else SIDE_EXISTING
        reasons.append(f"{keep}: higher resolution ({SIDE_NEW}={new.v_res} vs {SIDE_EXISTING}={existing.v_res})")
        return keep, "video", reasons, confidence

    new_hdr = _hdr_rank(new.v_hdr_format)
    ex_hdr = _hdr_rank(existing.v_hdr_format)
    if new_hdr != ex_hdr:
        keep = SIDE_NEW if new_hdr > ex_hdr else SIDE_EXISTING
        reasons.append(f"{keep}: better HDR ({SIDE_NEW}={new.v_hdr_format} vs {SIDE_EXISTING}={existing.v_hdr_format})")
        return keep, "video", reasons, confidence

    if new.v_bit_depth and existing.v_bit_depth and new.v_bit_depth != existing.v_bit_depth:
        keep = SIDE_NEW if new.v_bit_depth > existing.v_bit_depth else SIDE_EXISTING
        reasons.append(
            f"{keep}: higher bit depth ({SIDE_NEW}={new.v_bit_depth}-bit vs {SIDE_EXISTING}={existing.v_bit_depth}-bit)"
        )
        return keep, "video", reasons, confidence
    if (new.v_bit_depth is None) != (existing.v_bit_depth is None):
        confidence = "medium"

    new_vc = _vcodec_rank(new.v_codec)
    ex_vc = _vcodec_rank(existing.v_codec)
    if new_vc != ex_vc:
        keep = SIDE_NEW if new_vc > ex_vc else SIDE_EXISTING
        reasons.append(f"{keep}: better video codec ({SIDE_NEW}={new.v_codec} vs {SIDE_EXISTING}={existing.v_codec})")
        return keep, "video", reasons, confidence

    new_vbr, new_proxy = _video_bitrate_effective_bps(new)
    ex_vbr, ex_proxy = _video_bitrate_effective_bps(existing)
    if new_proxy or ex_proxy:
        confidence = "medium" if confidence == "high" else confidence
    if new_vbr and ex_vbr:
        # Only treat as meaningful if >=10% difference
        hi = max(new_vbr, ex_vbr)
        lo = min(new_vbr, ex_vbr)
        if lo > 0 and (hi / lo) >= 1.10:
            keep = SIDE_NEW if new_vbr > ex_vbr else SIDE_EXISTING
            suffix = " (proxy)" if (new_proxy or ex_proxy) else ""
            reasons.append(
                f"{keep}: higher effective bitrate{suffix} ({SIDE_NEW}={_human_bps(new_vbr)} vs {SIDE_EXISTING}={_human_bps(ex_vbr)})"
            )
            return keep, "video", reasons, confidence
    else:
        confidence = "low"

    # 2) AUDIO tie-breaker
    bn = _best_audio(new)
    be = _best_audio(existing)
    if not bn or not be:
        confidence = "low"
        return "TIE", "tie", ["video and audio could not be compared reliably"], confidence

    # codec rank: lower is better (reuse existing)
    if _codec_rank(bn.codec) != _codec_rank(be.codec):
        keep = SIDE_NEW if _codec_rank(bn.codec) < _codec_rank(be.codec) else SIDE_EXISTING
        reasons.append(f"{keep}: better audio codec ({SIDE_NEW}={bn.codec} vs {SIDE_EXISTING}={be.codec})")
        return keep, "audio", reasons, confidence

    if bn.atmos != be.atmos:
        keep = SIDE_NEW if bn.atmos else SIDE_EXISTING
        reasons.append(f"{keep}: Atmos present ({SIDE_NEW}={bn.atmos} vs {SIDE_EXISTING}={be.atmos})")
        return keep, "audio", reasons, confidence

    new_ch = _audio_channels_count(bn.channels)
    ex_ch = _audio_channels_count(be.channels)
    if new_ch != ex_ch:
        keep = SIDE_NEW if new_ch > ex_ch else SIDE_EXISTING
        reasons.append(f"{keep}: more audio channels ({SIDE_NEW}={bn.channels} vs {SIDE_EXISTING}={be.channels})")
        confidence = "medium" if confidence == "high" else confidence
        return keep, "audio", reasons, confidence

    # If we got here, they are effectively equal for decision purposes
    return "TIE", "tie", [f"{SIDE_NEW} and {SIDE_EXISTING} appear equivalent for video-first rules"], confidence


def _fmt_duration(dur_s: Optional[float]) -> str:
    if dur_s is None:
        return "?"
    m, s = divmod(int(dur_s + 0.5), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def _truncate(s: str, width: int) -> str:
    s = s or ""
    if width <= 0:
        return ""
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"


def _clean_reason(reason: str) -> str:
    # Remove redundant "NEW:" / "EXISTING:" prefixes for summary table
    r = (reason or "").strip()
    for p in (f"{SIDE_NEW}:", f"{SIDE_EXISTING}:"):
        if r.startswith(p):
            r = r[len(p) :].lstrip()
    return r


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare movie copies in two libraries (print-only).",
    )
    ap.add_argument("--path-a", default=DEFAULT_NEW_PATH, help=f"New copies (default: {DEFAULT_NEW_PATH})")
    ap.add_argument("--path-b", default=DEFAULT_EXISTING_PATH, help=f"Existing library (default: {DEFAULT_EXISTING_PATH})")
    ap.add_argument("--threads", type=int, default=8, help="Concurrent probes for matched movies (default: 8)")
    ap.add_argument(
        "--details",
        dest="details",
        action="store_true",
        help="Show full per-movie technical details (Section 3).",
    )
    ap.add_argument(
        "--strict-imdb",
        action="store_true",
        help="Only match movies by IMDb id (skip title/year matches).",
    )
    args = ap.parse_args()

    missing_bins = [b for b in ("ffprobe", "mkvmerge") if not _which_ok(b)]
    if missing_bins:
        print(f"ERROR: missing required binaries in PATH: {', '.join(missing_bins)}", file=sys.stderr)
        return 2

    print("=== Compare Movie Libraries ===")
    print(f"{SIDE_NEW} path:      {args.path_a}")
    print(f"{SIDE_EXISTING} path: {args.path_b}")
    print()

    a_index, a_problems = index_library(args.path_a, SIDE_NEW)
    b_index, b_problems = index_library(args.path_b, SIDE_EXISTING)
    for p in a_problems + b_problems:
        print(p)

    if args.strict_imdb:
        a_index = {k: v for k, v in a_index.items() if k[0] == "imdb"}
        b_index = {k: v for k, v in b_index.items() if k[0] == "imdb"}

    a_keys = set(a_index.keys())
    b_keys = set(b_index.keys())

    only_a = sorted(a_keys - b_keys)
    both = sorted(a_keys & b_keys)

    # Identify ambiguous keys (collisions)
    ambiguous: List[Tuple[str, str]] = []
    for k in both:
        if len(a_index.get(k, [])) != 1 or len(b_index.get(k, [])) != 1:
            ambiguous.append(k)
    both_unique = [k for k in both if k not in set(ambiguous)]

    print(f"=== 1) Movies in {SIDE_NEW} that are NOT in {SIDE_EXISTING} ===")
    print(f"Count: {len(only_a)}")
    if not only_a:
        print("(none)")
    else:
        for k in only_a:
            for e in a_index.get(k, []):
                warn = f" [{' ,'.join(e.warnings)}]" if e.warnings else ""
                print(f"- {k[0]}:{k[1]}  ::  {_fmt_identity(e)}  ::  {os.path.basename(e.folder)}{warn}")
    print()

    print(f"=== 2) Movies present in BOTH ({SIDE_NEW} vs {SIDE_EXISTING}) (recommendation summary) ===")
    print(f"Matched (unique): {len(both_unique)}")
    if ambiguous:
        print(f"Ambiguous keys (need manual review): {len(ambiguous)}")
    print()

    # Probe matched movies in parallel
    def probe_pair(k: Tuple[str, str]) -> Tuple[Tuple[str, str], Optional[MediaSummary], Optional[MediaSummary], List[str]]:
        notes: List[str] = []
        a_ent = a_index[k][0]
        b_ent = b_index[k][0]
        if not a_ent.mkv_path:
            notes.append("A:no_mkv")
            return k, None, None, notes
        if not b_ent.mkv_path:
            notes.append("B:no_mkv")
            return k, None, None, notes
        try:
            a_sum = summarize_media(a_ent.mkv_path)
        except Exception as e:
            notes.append(f"A:probe_failed({e})")
            a_sum = None
        try:
            b_sum = summarize_media(b_ent.mkv_path)
        except Exception as e:
            notes.append(f"B:probe_failed({e})")
            b_sum = None
        return k, a_sum, b_sum, notes

    @dataclass(frozen=True)
    class CompareResult:
        key: Tuple[str, str]
        a_ent: MovieEntry
        b_ent: MovieEntry
        a_sum: Optional[MediaSummary]
        b_sum: Optional[MediaSummary]
        notes: Tuple[str, ...]
        keep: str
        basis: str
        reasons: Tuple[str, ...]
        confidence: str

    def label_for(k: Tuple[str, str], a_ent: MovieEntry, b_ent: MovieEntry) -> str:
        # Always try to show a human name (Title (Year)) in summaries.
        # Prefer NEW side identity, fallback to EXISTING.
        ident = _fmt_identity(a_ent) or _fmt_identity(b_ent)

        # If we have an imdb id, include it too (even if ident is also an imdb id).
        imdb = a_ent.imdb or b_ent.imdb
        if imdb:
            # Avoid duplicate "tt..." only line
            if ident.startswith("tt"):
                # If ident is just imdb, try to enrich with title/year if present
                if (a_ent.title and a_ent.year) or (b_ent.title and b_ent.year):
                    ident = _fmt_identity(a_ent) if (a_ent.title and a_ent.year) else _fmt_identity(b_ent)
            return f"{k[0]}:{k[1]}  ::  {imdb}  ::  {ident}"

        return f"{k[0]}:{k[1]}  ::  {ident}"

    results: List[CompareResult] = []
    if not both_unique:
        print("(none)")
    else:
        with cf.ThreadPoolExecutor(max_workers=max(1, int(args.threads))) as ex:
            futs = {ex.submit(probe_pair, k): k for k in both_unique}
            for fut in cf.as_completed(futs):
                k, a_sum, b_sum, notes = fut.result()
                a_ent = a_index[k][0]
                b_ent = b_index[k][0]

                keep = "TIE"
                basis = "tie"
                conf = "low"
                reasons: List[str] = []
                if a_sum and b_sum:
                    keep, basis, reasons, conf = recommend_keep(a_sum, b_sum)
                else:
                    reasons = [f"probe failed for {SIDE_NEW} or {SIDE_EXISTING}"]

                results.append(
                    CompareResult(
                        key=k,
                        a_ent=a_ent,
                        b_ent=b_ent,
                        a_sum=a_sum,
                        b_sum=b_sum,
                        notes=tuple(notes),
                        keep=keep,
                        basis=basis,
                        reasons=tuple(reasons),
                        confidence=conf,
                    )
                )

    # Section 2: recommendation summary
    results.sort(key=lambda r: (r.key[0], r.key[1]))
    # Print a scan-friendly table (one line per movie)
    keep_new = sum(1 for r in results if r.keep == SIDE_NEW)
    keep_existing = sum(1 for r in results if r.keep == SIDE_EXISTING)
    ties = sum(1 for r in results if r.keep == "TIE")
    print(f"Summary: KEEP {SIDE_NEW}={keep_new}  KEEP {SIDE_EXISTING}={keep_existing}  TIE={ties}")
    print()

    # Sort by action first, then title for quick scanning
    action_order = {SIDE_NEW: 0, SIDE_EXISTING: 1, "TIE": 2}
    def sort_title(r: CompareResult) -> str:
        t = r.a_ent.title or r.b_ent.title or ""
        y = r.a_ent.year or r.b_ent.year or ""
        return f"{t} {y}".strip().lower()

    results_sorted = sorted(results, key=lambda r: (action_order.get(r.keep, 9), sort_title(r)))

    # Column widths (tuned for typical terminal widths)
    w_action = 12
    w_basis = 6
    w_conf = 6
    w_title = 38
    w_imdb = 10
    header = (
        f"{'ACTION':<{w_action}}  "
        f"{'BASIS':<{w_basis}}  "
        f"{'CONF':<{w_conf}}  "
        f"{'TITLE':<{w_title}}  "
        f"{'IMDB':<{w_imdb}}  "
        f"WHY"
    )
    print(header)
    print("-" * len(header))

    for r in results_sorted:
        title = _fmt_identity(r.a_ent) if (r.a_ent.title and r.a_ent.year) else _fmt_identity(r.b_ent)
        imdb = r.a_ent.imdb or r.b_ent.imdb or ""

        action = "TIE" if r.keep == "TIE" else f"KEEP {r.keep}"
        basis = "-" if r.keep == "TIE" else r.basis
        conf = r.confidence
        why = _clean_reason(r.reasons[0]) if r.reasons else ""
        if r.keep in {SIDE_NEW, SIDE_EXISTING} and len(r.reasons) > 1:
            why = why + " (+more)"
        if r.notes:
            # keep notes short in summary view
            why = (why + f" [notes:{len(r.notes)}]").strip()

        print(
            f"{action:<{w_action}}  "
            f"{basis:<{w_basis}}  "
            f"{conf:<{w_conf}}  "
            f"{_truncate(title, w_title):<{w_title}}  "
            f"{_truncate(imdb, w_imdb):<{w_imdb}}  "
            f"{why}"
        )
    print()

    if args.details:
        # Section 3: full details (current detailed dump)
        print(f"=== 3) Movies present in BOTH ({SIDE_NEW} vs {SIDE_EXISTING}) (full details) ===")
        print(f"Count: {len(results)}")
        print()
        if not results:
            print("(none)")
        else:
            for r in results:
                print(f"--- {label_for(r.key, r.a_ent, r.b_ent)}")
                print(f" {SIDE_NEW} folder: {os.path.basename(r.a_ent.folder)}")
                print(f" {SIDE_EXISTING} folder: {os.path.basename(r.b_ent.folder)}")

                if r.a_sum:
                    print(f" {SIDE_NEW} file: {os.path.basename(r.a_sum.mkv_path)}")
                    print(f"   size={_human_bytes(r.a_sum.size_bytes)}  dur={_fmt_duration(r.a_sum.duration_s)}")
                    print(f"   {_fmt_video(r.a_sum)}")
                    print(f"   {_fmt_hdr(r.a_sum)}")
                    print(f"   {_fmt_audio_tracks(r.a_sum)}")
                else:
                    print(f" {SIDE_NEW} file: (probe failed)")

                if r.b_sum:
                    print(f" {SIDE_EXISTING} file: {os.path.basename(r.b_sum.mkv_path)}")
                    print(f"   size={_human_bytes(r.b_sum.size_bytes)}  dur={_fmt_duration(r.b_sum.duration_s)}")
                    print(f"   {_fmt_video(r.b_sum)}")
                    print(f"   {_fmt_hdr(r.b_sum)}")
                    print(f"   {_fmt_audio_tracks(r.b_sum)}")
                else:
                    print(f" {SIDE_EXISTING} file: (probe failed)")

                if r.keep in {SIDE_NEW, SIDE_EXISTING}:
                    print(f" RECOMMEND: KEEP {r.keep} (basis={r.basis}, confidence={r.confidence})")
                else:
                    print(f" RECOMMEND: TIE (confidence={r.confidence})")
                for reason in r.reasons:
                    print(f"  - {reason}")
                if r.notes:
                    print(" Notes: " + " ; ".join(r.notes))
                print()

    if ambiguous:
        print("=== Ambiguous matches (skipped from detailed comparison) ===")
        for k in ambiguous:
            print(f"- {k[0]}:{k[1]}")
            print("  A candidates:")
            for e in a_index.get(k, []):
                print(f"   - {os.path.basename(e.folder)} :: {_fmt_identity(e)}")
            print("  B candidates:")
            for e in b_index.get(k, []):
                print(f"   - {os.path.basename(e.folder)} :: {_fmt_identity(e)}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

