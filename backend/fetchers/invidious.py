import json
from curl_cffi import requests as curl_requests
from .base import BaseFetcher

class InvidiousFetcher(BaseFetcher):
    # List of public instances (will try each until one works)
    INSTANCES = [
        "https://invidious.snopyta.org",
        "https://inv.vern.cc",
        "https://yewtu.be",
        "https://invidious.perennialte.ch",
        "https://invidious.mint.lgbt",
    ]

    def fetch_formats(self, url):
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return []
        # Try each instance
        for instance in self.INSTANCES:
            try:
                # Get video info via Invidious API
                api_url = f"{instance}/api/v1/videos/{self._extract_video_id(url)}"
                response = curl_requests.get(api_url, timeout=15, impersonate="chrome150")
                if response.status_code == 200:
                    data = response.json()
                    formats = []
                    # Invidious returns formats in 'adaptiveFormats' and 'formatStreams'
                    for f in data.get('adaptiveFormats', []):
                        # Ensure we have a URL
                        if 'url' not in f:
                            continue
                        # Determine if video/audio
                        has_video = 'video' in f.get('type', '').lower()
                        has_audio = 'audio' in f.get('type', '').lower()
                        # Map quality
                        quality = f.get('qualityLabel') or f.get('quality') or 'unknown'
                        formats.append({
                            'format_id': f.get('itag', 'unknown'),
                            'url': f['url'],
                            'ext': 'mp4' if 'mp4' in f['url'] else 'm3u8',
                            'quality': quality,
                            'has_video': has_video,
                            'has_audio': has_audio,
                            'size': None,
                            'height': f.get('height'),
                            'width': f.get('width'),
                            'fps': f.get('fps'),
                            'note': f.get('mimeType', ''),
                        })
                    # Also add formatStreams (progressive)
                    for f in data.get('formatStreams', []):
                        if 'url' not in f:
                            continue
                        has_video = 'video' in f.get('type', '').lower()
                        has_audio = 'audio' in f.get('type', '').lower()
                        quality = f.get('qualityLabel') or f.get('quality') or 'unknown'
                        formats.append({
                            'format_id': f.get('itag', 'unknown'),
                            'url': f['url'],
                            'ext': 'mp4' if 'mp4' in f['url'] else 'm3u8',
                            'quality': quality,
                            'has_video': has_video,
                            'has_audio': has_audio,
                            'size': None,
                            'height': f.get('height'),
                            'width': f.get('width'),
                            'fps': f.get('fps'),
                            'note': f.get('mimeType', ''),
                        })
                    if formats:
                        return formats
            except Exception as e:
                print(f"Invidious instance {instance} failed: {e}")
                continue
        return []

    def _extract_video_id(self, url):
        # Simple extraction for YouTube URLs
        import re
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&?/]+)',
            r'youtube\.com\/embed\/([^/?]+)',
            r'youtube\.com\/v\/([^/?]+)',
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return url  # fallback