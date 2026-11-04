import re
import json
from curl_cffi import requests as curl_requests
from .base import BaseFetcher

class YouTubeFetcher(BaseFetcher):
    def fetch_formats(self, url):
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return []
        try:
            # Use curl_cffi to get the watch page with a browser fingerprint
            response = curl_requests.get(url, impersonate="chrome150", timeout=20)
            if response.status_code != 200:
                return []
            html = response.text
            # Try to extract initial player response JSON
            match = re.search(r'var ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
            if not match:
                match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group(1))
            formats = []
            # Extract from streamingData
            streaming = data.get('streamingData', {})
            for f in streaming.get('formats', []):
                formats.append(self._format_from_yt(f))
            for f in streaming.get('adaptiveFormats', []):
                formats.append(self._format_from_yt(f))
            return formats
        except Exception as e:
            print(f"YouTubeFetcher error: {e}")
            return []

    def _format_from_yt(self, f):
        has_video = f.get('mimeType', '').startswith('video')
        has_audio = f.get('mimeType', '').startswith('audio')
        return {
            'format_id': f.get('itag', 'unknown'),
            'url': f.get('url'),
            'ext': 'mp4' if 'mp4' in f.get('mimeType', '') else 'm3u8',
            'quality': f.get('qualityLabel') or f.get('quality') or 'unknown',
            'has_video': has_video,
            'has_audio': has_audio,
            'size': f.get('contentLength'),
            'height': f.get('height'),
            'width': f.get('width'),
            'fps': f.get('fps'),
            'note': f.get('mimeType', ''),
        }