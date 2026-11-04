"""Standalone cross-platform yt-dlp downloader."""
import os
import shutil
import subprocess
import sys
import tempfile


def _yt_dlp_command():
    executable = os.getenv("YTDLP_PATH") or shutil.which("yt-dlp")
    return [executable] if executable else [sys.executable, "-m", "yt_dlp"]


class MediaDownloader:
    @staticmethod
    def download(url, format_id="bestvideo+bestaudio/best", output_path=None):
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
        cmd = _yt_dlp_command() + ["-f", format_id, "-o", output_path, "--quiet", "--no-warnings", "--merge-output-format", "mp4"]
        if "bilibili.com" in url or "bilibili.tv" in url or "b23.tv" in url:
            cmd += [
                "--add-headers", "Referer: https://www.bilibili.com/",
                "--add-headers", "Origin: https://www.bilibili.com",
                "--add-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "--add-headers", "Range: bytes=0-",
                "--retries", "20", "--fragment-retries", "20",
                "--retry-sleep", "http:1:5", "--retry-sleep", "fragment:1:5",
            ]
        cookie_file = os.getenv("UMP_COOKIES_FILE", "").strip()
        browser = os.getenv("UMP_COOKIES_FROM_BROWSER", "").strip()
        if cookie_file:
            cmd += ["--cookies", os.path.abspath(os.path.expanduser(cookie_file))]
        elif browser:
            cmd += ["--cookies-from-browser", browser]
        cmd.append(url)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            raise RuntimeError(f"Download failed (exit {result.returncode}): {(result.stderr or result.stdout)[-1200:]}")
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Download error: {exc}") from exc
