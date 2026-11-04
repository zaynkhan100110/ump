import re
from curl_cffi import requests as curl_requests
from .base import BaseFetcher

class ScraperFetcher(BaseFetcher):
    """
    Fallback scraper that tries to extract video URLs from HTML pages.
    Works for sites where yt-dlp struggles.
    """
    def fetch_formats(self, url):
        try:
            # Try to fetch the page with a browser fingerprint
            response = curl_requests.get(
                url,
                impersonate="chrome150",
                timeout=20,
                headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
                }
            )
            if response.status_code != 200:
                return []

            html = response.text
            formats = []

            # Try to find video URLs in the page
            # Common patterns: video src, source tags, JSON blobs
            patterns = [
                r'(https?://[^\s"\']+\.mp4)',
                r'(https?://[^\s"\']+\.m3u8)',
                r'(https?://[^\s"\']+playlist\.m3u8[^\s"\']*)',
                r'src="([^"]+\.mp4)"',
                r'src="([^"]+\.m3u8)"',
                r'"videoUrl"\s*:\s*"([^"]+)"',
                r'"contentUrl"\s*:\s*"([^"]+)"',
                r'"file"\s*:\s*"([^"]+)"',
            ]

            seen_urls = set()
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for video_url in matches:
                    if video_url.startswith('http') and video_url not in seen_urls:
                        seen_urls.add(video_url)
                        ext = 'mp4' if '.mp4' in video_url else 'm3u8'
                        formats.append({
                            'format_id': f'scraper_{len(formats)}',
                            'url': video_url,
                            'ext': ext,
                            'quality': 'best',
                            'has_video': True,
                            'has_audio': True,
                            'note': 'Scraped from page',
                            'size': None,
                        })

            return formats

        except Exception as e:
            print(f"ScraperFetcher error: {e}")
            return []