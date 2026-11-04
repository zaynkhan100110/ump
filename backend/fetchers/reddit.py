# backend/fetchers/reddit.py
import re
import json
from curl_cffi import requests as curl_requests
from .base import BaseFetcher

class RedditFetcher(BaseFetcher):
    def fetch_formats(self, url):
        if 'reddit.com' not in url and 'redd.it' not in url:
            return []

        # Resolve share links (like /r/.../s/...)
        if '/s/' in url or ('/r/' in url and '/comments/' not in url):
            try:
                resp = curl_requests.get(url, impersonate='chrome150', timeout=15, allow_redirects=True)
                url = resp.url
            except:
                pass

        # Extract post ID
        post_id = None
        match = re.search(r'/comments/([a-zA-Z0-9]+)', url)
        if match:
            post_id = match.group(1)
        else:
            match = re.search(r'redd\.it/([a-zA-Z0-9]+)', url)
            if match:
                post_id = match.group(1)

        if not post_id:
            return []

        api_url = f"https://www.reddit.com/by_id/t3_{post_id}.json"
        try:
            response = curl_requests.get(
                api_url,
                impersonate="chrome150",
                timeout=15,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if response.status_code != 200:
                return []

            data = response.json()
            children = data[0]['data']['children']
            if not children:
                return []

            post_data = children[0]['data']
            media = post_data.get('secure_media') or post_data.get('media')
            if media and 'reddit_video' in media:
                video_info = media['reddit_video']
                fallback_url = video_info.get('fallback_url')
                if fallback_url:
                    return [{
                        'format_id': 'reddit_mp4',
                        'url': fallback_url,
                        'ext': 'mp4',
                        'quality': video_info.get('quality', 'unknown'),
                        'has_video': True,
                        'has_audio': True,
                        'note': 'Reddit video (direct)',
                        'size': None
                    }]
            return []
        except Exception as e:
            print(f"RedditFetcher error: {e}")
            return []