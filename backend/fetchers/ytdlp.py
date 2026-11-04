"""Generic yt-dlp-backed format fetcher with cross-platform executable lookup."""
import json
import os
import shutil
import subprocess
import sys
from .base import BaseFetcher


def _command():
    executable = os.getenv("YTDLP_PATH") or shutil.which("yt-dlp")
    return [executable] if executable else [sys.executable, "-m", "yt_dlp"]


def _runtime_args():
    deno = shutil.which("deno")
    if deno:
        return ["--js-runtimes", f"deno:{deno}"]
    node = shutil.which("node")
    return ["--js-runtimes", f"node:{node}"] if node else []


class YtDlpFetcher(BaseFetcher):
    def fetch_formats(self, url):
        cmd = _command() + ["--no-warnings", "--no-playlist", "--dump-single-json", "--skip-download"]
        cmd += _runtime_args()
        if "bilibili" in url.lower() or "b23.tv" in url.lower():
            cmd += ["--add-headers", "Origin: https://www.bilibili.com", "--add-headers", "Referer: https://www.bilibili.com/"]
        cookie_file = os.getenv("UMP_COOKIES_FILE", "").strip()
        browser = os.getenv("UMP_COOKIES_FROM_BROWSER", "").strip()
        if cookie_file:
            cmd += ["--cookies", os.path.abspath(os.path.expanduser(cookie_file))]
        elif browser:
            cmd += ["--cookies-from-browser", browser]
        cmd.append(url)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(os.getenv("UMP_METADATA_TIMEOUT", "150")))
            if result.returncode:
                return []
            data = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return []
        formats = []
        for item in data.get("formats") or []:
            fid = str(item.get("format_id") or "")
            if not fid or "storyboard" in fid.lower() or (item.get("height") is not None and item["height"] < 100):
                continue
            video = item.get("vcodec") not in (None, "none")
            audio = item.get("acodec") not in (None, "none")
            formats.append({
                "format_id": f"{fid}+bestaudio/best" if video and not audio else fid,
                "url": item.get("url"), "ext": item.get("ext") or "unknown",
                "quality": item.get("format_note") or item.get("resolution") or fid,
                "has_video": video, "has_audio": audio,
                "size": item.get("filesize") or item.get("filesize_approx"),
                "height": item.get("height"), "width": item.get("width"), "fps": item.get("fps"),
                "note": item.get("format_note") or "",
            })
        return formats
