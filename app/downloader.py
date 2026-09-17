from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp

# Automatically locate ffmpeg executable
def _get_ffmpeg_location() -> str | None:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


# Regex patterns for Pinterest pins, boards, watch/reels, country domains, and short links
PINTEREST_REGEX = re.compile(
    r"https?://(?:[a-zA-Z0-9-]+\.)?pinterest\.[a-zA-Z0-9.]+(?:/[^\s]*)?",
    re.IGNORECASE,
)
PIN_IT_REGEX = re.compile(r"https?://(?:www\.)?pin\.it/[a-zA-Z0-9_-]+", re.IGNORECASE)

MAX_DOWNLOAD_MB = float(os.getenv("MAX_DOWNLOAD_MB", "45"))
MAX_DOWNLOAD_BYTES = int(MAX_DOWNLOAD_MB * 1024 * 1024)


def extract_pinterest_url(text: str) -> str | None:
    """Extract the first Pinterest URL from a text message."""
    if not text:
        return None

    # Try pin.it short link first
    pin_it_match = PIN_IT_REGEX.search(text)
    if pin_it_match:
        return pin_it_match.group(0).strip()

    # Try general pinterest.* link
    pinterest_match = PINTEREST_REGEX.search(text)
    if pinterest_match:
        return pinterest_match.group(0).strip()

    return None


def is_pinterest_url(url: str) -> bool:
    """Check if the provided string is a valid Pinterest URL."""
    return extract_pinterest_url(url) is not None


def _safe_title(value: str | None) -> str:
    if not value or value.strip() == "":
        return "pinterest_video"
    cleaned = re.sub(r"[^\w\-. ]+", "_", value, flags=re.UNICODE).strip()
    return cleaned[:100] or "pinterest_video"


def _progress_hook_factory(limit_bytes: int):
    def hook(data: dict[str, Any]) -> None:
        if data.get("status") != "downloading":
            return
        downloaded = data.get("downloaded_bytes") or 0
        if downloaded > limit_bytes:
            raise RuntimeError(
                f"Video is larger than the configured {MAX_DOWNLOAD_MB:g} MB limit."
            )

    return hook


def download_pinterest_video(url: str) -> dict[str, Any]:
    """Download video from Pinterest and extract media metadata + direct download links."""
    clean_url = extract_pinterest_url(url)
    if not clean_url:
        raise ValueError("Please provide a valid Pinterest or pin.it link.")

    temp_dir = Path(tempfile.mkdtemp(prefix="pinterest-bot-"))
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    ffmpeg_path = _get_ffmpeg_location()

    options: dict[str, Any] = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "outtmpl": output_template,
        "format": "best[ext=mp4]/bestvideo+bestaudio/best",
        "max_filesize": MAX_DOWNLOAD_BYTES,
        "progress_hooks": [_progress_hook_factory(MAX_DOWNLOAD_BYTES)],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        },
    }

    if ffmpeg_path:
        options["ffmpeg_location"] = ffmpeg_path
        options["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                raise RuntimeError("Pinterest returned no media information for this link.")

            # Find best direct video URL from formats or url field
            direct_url = info.get("url")
            if not direct_url and "formats" in info:
                mp4_formats = [
                    f for f in info.get("formats", [])
                    if f.get("ext") == "mp4" and f.get("url")
                ]
                if mp4_formats:
                    direct_url = mp4_formats[-1].get("url")

            filename = ydl.prepare_filename(info)
            # If converted to mp4
            if not filename.endswith(".mp4"):
                mp4_cand = Path(filename).with_suffix(".mp4")
                if mp4_cand.exists():
                    filename = str(mp4_cand)


        path = Path(filename)
        if not path.exists():
            candidates = list(temp_dir.glob("*.mp4")) or list(temp_dir.glob("*"))
            if not candidates:
                raise RuntimeError("Download finished but no media file was produced.")
            path = candidates[0]

        size = path.stat().st_size
        if size > MAX_DOWNLOAD_BYTES:
            path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Video is larger than {MAX_DOWNLOAD_MB:g} MB limit."
            )

        title = info.get("title") or info.get("description") or "Pinterest Video"

        return {
            "path": str(path),
            "temp_dir": str(temp_dir),
            "title": _safe_title(title),
            "webpage_url": info.get("webpage_url") or clean_url,
            "direct_url": direct_url,
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "width": info.get("width"),
            "height": info.get("height"),
            "size": size,
        }
    except Exception:
        for item in temp_dir.glob("*"):
            try:
                item.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass
        raise
