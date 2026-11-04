# backend/fetchers/rumble.py
import re
import json
import subprocess
import logging
import os
import shutil
import sys
from urllib.parse import quote
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from .base import BaseFetcher
# We import the helper from app.py? Better to duplicate here or import from utils.
# Since we have the helper in app.py, we can import from utils if defined there.
# For simplicity, I'll redefine the helper inside this file (or import from utils if you prefer).
# To avoid circular imports, we'll copy the helper function here.
# Or we can import from utils if you have it.
# I'll assume utils.py exists with get_rumble_embed_url.
# But to be safe, I'll use a local version.
try:
    from utils import get_rumble_embed_url
except ImportError:
    # fallback: define a simple version
    def get_rumble_embed_url(url):
        # ... simplified version (but we already have it in app.py)
        pass

logger = logging.getLogger(__name__)

class RumbleFetcher(BaseFetcher):
    def fetch_formats(self, url):
        if 'rumble.com' not in url:
            return []

        is_short = '/shorts/' in url.lower()
        is_embed = '/embed/' in url.lower()
        logger.info(f"Rumble: {'SHORT' if is_short else 'VIDEO'} URL {url}")

        # ---------- SHORT ----------
        if is_short:
            return self._handle_short(url)

        # ---------- EMBED ----------
        if is_embed:
            return self._ytdlp_json(url)

        # ---------- NORMAL VIDEO PAGE ----------
        embed_url = self._get_embed_url_from_page(url)
        if embed_url:
            formats = self._ytdlp_json(embed_url)
            if formats:
                return formats

        # Fallback: direct page scraping
        return self._direct_page_fallback(url)

    def _get_embed_url_from_page(self, url):
        # Try oEmbed
        try:
            oembed_url = f"https://rumble.com/api/Media/oembed.json?url={quote(url)}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
            resp = curl_requests.get(oembed_url, impersonate='chrome150', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if 'html' in data:
                    match = re.search(r'src=["\']([^"\']+)["\']', data['html'])
                    if match:
                        embed_src = match.group(1)
                        embed_match = re.search(r'/embed/([^/?#]+)', embed_src)
                        if embed_match:
                            embed_id = embed_match.group(1)
                            if not embed_id.startswith('v'):
                                embed_id = 'v' + embed_id
                            return f'https://rumble.com/embed/{embed_id}/'
        except:
            pass

        # Try regex from URL
        match = re.search(r'rumble\.com/v([a-zA-Z0-9]+)', url)
        if match:
            video_id = match.group(1)
            if not video_id.startswith('v'):
                video_id = 'v' + video_id
            return f'https://rumble.com/embed/{video_id}/'

        # Try to fetch the page
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
            resp = curl_requests.get(url, impersonate='chrome150', timeout=20)
            if resp.status_code == 200:
                html = resp.text
                match = re.search(r'"embedUrl"\s*:\s*"([^"]+)"', html)
                if match:
                    embed_url = match.group(1).replace('\\/', '/')
                    if 'rumble.com/embed/' in embed_url:
                        return embed_url
                match = re.search(r'videoId\s*:\s*"([^"]+)"', html)
                if match:
                    video_id = match.group(1)
                    if not video_id.startswith('v'):
                        video_id = 'v' + video_id
                    return f'https://rumble.com/embed/{video_id}/'
        except:
            pass
        return None

    # ---------- SHORT HANDLER ----------
    def _handle_short(self, url):
        session = self._get_session()
        headers = self._get_headers()
        try:
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception as e:
            logger.error(f"Rumble Short fetch error: {e}")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        direct_mp4 = None
        video_tag = soup.find('video')
        if video_tag:
            source = video_tag.find('source')
            if source and source.get('src'):
                direct_mp4 = source.get('src')
            elif video_tag.get('src'):
                direct_mp4 = video_tag.get('src')
        if not direct_mp4:
            rum_video = soup.find('rum-video', attrs={'url': True})
            if rum_video:
                direct_mp4 = rum_video.get('url')
        if not direct_mp4:
            match = re.search(r'<rum-video[^>]*url=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if match:
                direct_mp4 = match.group(1)

        if direct_mp4 and '.mp4' in direct_mp4:
            if direct_mp4.startswith('//'):
                direct_mp4 = 'https:' + direct_mp4
            elif not direct_mp4.startswith('http'):
                direct_mp4 = 'https://rumble.com' + direct_mp4
            logger.info(f"Rumble Short: direct MP4: {direct_mp4}")
            return [{
                'format_id': 'rumble_short_mp4',
                'url': direct_mp4,
                'ext': 'mp4',
                'quality': 'best',
                'has_video': True,
                'has_audio': True,
                'note': 'Direct MP4 (download directly)',
                'size': None,
                'height': None,
                'width': None,
                'fps': None,
                '_direct': True,
            }]
        return []

    # ---------- YT-DLP JSON with filtering ----------
    def _ytdlp_json(self, url):
        executable = os.getenv('YTDLP_PATH') or shutil.which('yt-dlp')
        cmd = ([executable] if executable else [sys.executable, '-m', 'yt_dlp']) + [
            '--impersonate', 'chrome-131',
            '--legacy-server-connect',
            '--no-warnings',
            '--quiet',
            '--dump-json',
            '--add-header', 'Origin: https://rumble.com',
            '--add-header', 'Referer: https://rumble.com/',
            '--add-header', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            url
        ]
        try:
            logger.info(f"Rumble: running yt-dlp JSON for {url}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
            if result.returncode != 0:
                logger.warning(f"yt-dlp JSON failed: {result.stderr[:200]}")
                return None

            data = json.loads(result.stdout)
            formats = []
            for f in data.get('formats', []):
                # Safe handling of format_note (may be None)
                note = f.get('format_note')
                if note is None:
                    note = ''
                note = note.lower()

                format_id = f.get('format_id', '')
                # Skip storyboards
                if 'storyboard' in note or 'storyboard' in format_id:
                    continue

                height = f.get('height')
                # Skip very low resolution (likely thumbnails)
                if height is not None and height < 100:
                    continue

                has_video = f.get('vcodec', 'none') != 'none'
                has_audio = f.get('acodec', 'none') != 'none'
                res = f.get('resolution') or f.get('format_note')
                if not res and height:
                    res = f"{height}p"
                elif not res:
                    res = f.get('format_id', 'unknown')

                formats.append({
                    'format_id': format_id,
                    'url': f.get('url'),
                    'ext': f.get('ext', 'unknown'),
                    'quality': res,
                    'has_video': has_video,
                    'has_audio': has_audio,
                    'size': f.get('filesize') or f.get('filesize_approx'),
                    'height': height,
                    'width': f.get('width'),
                    'fps': f.get('fps'),
                    'note': note or '',
                })
            if formats:
                logger.info(f"Rumble: yt-dlp JSON returned {len(formats)} formats")
                return formats
        except Exception as e:
            logger.error(f"Rumble yt-dlp JSON error: {e}")
        return None

    # ---------- DIRECT PAGE FALLBACK (unchanged) ----------
    def _direct_page_fallback(self, url):
        session = self._get_session()
        headers = self._get_headers()
        try:
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception as e:
            logger.error(f"Rumble page fallback fetch error: {e}")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        video_tag = soup.find('video')
        if video_tag:
            source = video_tag.find('source')
            mp4_url = source.get('src') if source else video_tag.get('src')
            if mp4_url and ('.mp4' in mp4_url or '.m3u8' in mp4_url):
                if mp4_url.startswith('//'):
                    mp4_url = 'https:' + mp4_url
                elif not mp4_url.startswith('http'):
                    mp4_url = 'https://rumble.com' + mp4_url
                return [{
                    'format_id': 'rumble_direct_video',
                    'url': mp4_url,
                    'ext': 'mp4' if '.mp4' in mp4_url else 'm3u8',
                    'quality': 'best',
                    'has_video': True,
                    'has_audio': True,
                    'note': 'Direct from page',
                    'size': None,
                    'height': None,
                    'width': None,
                    'fps': None,
                }]

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                match = re.search(r'"mp4"\s*:\s*"([^"]+)"', script.string)
                if match:
                    mp4_url = match.group(1).replace('\\/', '/')
                    if mp4_url.startswith('http') and '.mp4' in mp4_url:
                        return [{
                            'format_id': 'rumble_script_mp4',
                            'url': mp4_url,
                            'ext': 'mp4',
                            'quality': 'best',
                            'has_video': True,
                            'has_audio': True,
                            'note': 'MP4 from script',
                            'size': None,
                            'height': None,
                            'width': None,
                            'fps': None,
                        }]
                match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', script.string)
                if match:
                    hls_url = match.group(1)
                    return [{
                        'format_id': 'rumble_hls',
                        'url': hls_url,
                        'ext': 'm3u8',
                        'quality': 'best',
                        'has_video': True,
                        'has_audio': True,
                        'note': 'HLS manifest from script',
                        'size': None,
                        'height': None,
                        'width': None,
                        'fps': None,
                    }]
        return []

    # ---------- HELPERS ----------
    def _get_session(self):
        session = curl_requests.Session()
        session.impersonate = 'chrome150'
        return session

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://rumble.com/',
            'Origin': 'https://rumble.com',
        }