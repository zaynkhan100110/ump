"""Bilibili format extraction helper.

The main Flask API currently uses the same yt-dlp pipeline as other platforms;
this helper remains available to integrations that instantiate fetchers directly.
It intentionally does not assume Chrome is installed or force browser-cookie access.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import BaseFetcher


def _yt_dlp_command() -> list[str]:
    configured = os.getenv("YTDLP_PATH") or shutil.which("yt-dlp")
    return [configured] if configured else [sys.executable, "-m", "yt_dlp"]


class BilibiliFetcher(BaseFetcher):
    def fetch_formats(self, url):
        if not url or not any(host in url.lower() for host in ("bilibili.com", "bilibili.tv", "b23.tv")):
            return []

        cmd = _yt_dlp_command() + [
            "--no-warnings", "--no-playlist", "--dump-single-json", "--skip-download",
            "--socket-timeout", os.getenv("UMP_SOCKET_TIMEOUT", "30"),
            "--add-headers", "Origin: https://www.bilibili.com",
            "--add-headers", "Referer: https://www.bilibili.com/",
            "--add-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "--add-headers", "Range: bytes=0-",
            "--add-headers", "Accept-Language: en-US,en;q=0.9",
        ]
        cookie_file = os.getenv("UMP_COOKIES_FILE", "").strip()
        browser = os.getenv("UMP_COOKIES_FROM_BROWSER", "").strip()
        if cookie_file:
            path = Path(cookie_file).expanduser().resolve()
            if not path.is_file():
                return []
            cmd += ["--cookies", str(path)]
        elif browser:
            cmd += ["--cookies-from-browser", browser]
        cmd.append(url)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=int(os.getenv("UMP_METADATA_TIMEOUT", "150")), check=False,
            )
            if result.returncode:
                return []
            info = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return []

        formats = []
        for item in info.get("formats") or []:
            if not item.get("url"):
                continue
            format_id = str(item.get("format_id") or "")
            if not format_id or "storyboard" in format_id.lower():
                continue
            if item.get("height") is not None and item["height"] < 100:
                continue
            formats.append({
                "format_id": format_id,
                "url": item["url"],
                "ext": item.get("ext") or "unknown",
                "quality": item.get("format_note") or item.get("resolution") or format_id,
                "has_video": item.get("vcodec") not in (None, "none"),
                "has_audio": item.get("acodec") not in (None, "none"),
                "size": item.get("filesize") or item.get("filesize_approx"),
                "height": item.get("height"),
                "width": item.get("width"),
                "fps": item.get("fps"),
                "note": item.get("format_note") or "",
            })
        return formats
