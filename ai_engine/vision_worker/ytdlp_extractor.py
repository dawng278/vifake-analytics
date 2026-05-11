"""
yt-dlp Metadata Extractor for ViFake Analytics.

Fetches YouTube/TikTok/Facebook video metadata without downloading the video.
Uses yt-dlp with --skip-download and a 10-second timeout.

Extracted fields (all safe for scam detection, no PII):
  title, description, uploader, view_count, like_count,
  comment_count, upload_date, duration, tags, categories,
  webpage_url, thumbnail
"""
import logging
import json
import subprocess
import shutil
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Check yt-dlp availability
_YTDLP_BIN = shutil.which("yt-dlp")
_YTDLP_AVAILABLE = _YTDLP_BIN is not None

if not _YTDLP_AVAILABLE:
    try:
        import yt_dlp  # noqa: F401 — importable as Python module
        _YTDLP_AVAILABLE = True
        _YTDLP_BIN = None  # will use Python API path
    except ImportError:
        logger.warning("yt-dlp not installed. Video metadata extraction will be skipped.")


_SAFE_FIELDS = [
    "title", "description", "uploader", "uploader_id",
    "view_count", "like_count", "comment_count",
    "upload_date", "duration", "tags", "categories",
    "webpage_url", "thumbnail", "age_limit",
    "channel", "channel_id", "channel_follower_count",
]


def _extract_via_python_api(url: str, timeout: int = 10) -> Dict:
    """Extract metadata using yt-dlp Python API (no subprocess)."""
    import yt_dlp

    # Try with impersonation first (needed for TikTok), fall back without it
    for impersonate in ("chrome", None):
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": timeout,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        }
        if impersonate:
            ydl_opts["impersonate"] = impersonate
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return {k: info.get(k) for k in _SAFE_FIELDS if info.get(k) is not None}
        except Exception as e:
            if impersonate and "impersonat" in str(e).lower():
                continue  # try without impersonation
            raise
    return {}


def _extract_via_cli(url: str, timeout: int = 10) -> Dict:
    """Extract metadata using yt-dlp CLI subprocess."""
    cmd = [
        _YTDLP_BIN,
        "--dump-json",
        "--no-playlist",
        "--skip-download",
        "--socket-timeout", str(timeout),
        "--quiet",
        "--impersonate", "chrome",  # bypass TikTok bot protection
        url,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp exited {result.returncode}: {result.stderr[:200]}")
    info = json.loads(result.stdout)
    return {k: info.get(k) for k in _SAFE_FIELDS if info.get(k) is not None}


def extract_video_metadata(url: str, timeout: int = 10) -> Dict:
    """Fetch video metadata from a URL using yt-dlp (no download).

    Args:
        url: YouTube / TikTok / Facebook video URL.
        timeout: Socket timeout in seconds (default 10).

    Returns:
        Dict with metadata fields, or empty dict on failure.
    """
    if not _YTDLP_AVAILABLE:
        return {}

    # Try CLI first (if available), then Python API as fallback
    extractors = []
    if _YTDLP_BIN:
        extractors.append(("cli", lambda: _extract_via_cli(url, timeout)))
    extractors.append(("python_api", lambda: _extract_via_python_api(url, timeout)))

    for name, fn in extractors:
        try:
            meta = fn()
            if meta:
                logger.info(
                    f"📹 yt-dlp [{name}] metadata: title='{str(meta.get('title',''))[:60]}' "
                    f"views={meta.get('view_count')} duration={meta.get('duration')}s"
                )
                return meta
        except subprocess.TimeoutExpired:
            logger.warning(f"yt-dlp [{name}] timed out for {url[:80]}")
        except Exception as e:
            logger.warning(f"yt-dlp [{name}] failed ({url[:80]}): {e}")

    return {}


def build_text_from_metadata(meta: Dict) -> str:
    """Combine title + description + tags into a single text string for NLP."""
    parts = []
    if meta.get("title"):
        parts.append(meta["title"])
    if meta.get("description"):
        parts.append(meta["description"][:500])  # cap description length
    if meta.get("tags") and isinstance(meta["tags"], list):
        parts.append(" ".join(meta["tags"][:20]))
    if meta.get("categories") and isinstance(meta["categories"], list):
        parts.append(" ".join(meta["categories"]))
    return " ".join(parts).strip()
