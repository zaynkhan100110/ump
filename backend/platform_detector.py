"""Strict hostname-based media platform detection."""
from urllib.parse import urlparse

PLATFORM_HOSTS = {
    'youtube': {'youtube.com', 'youtu.be', 'youtube-nocookie.com'},
    'tiktok': {'tiktok.com', 'vt.tiktok.com', 'vm.tiktok.com'},
    'twitter': {'twitter.com', 'x.com', 't.co'},
    'vimeo': {'vimeo.com'},
    'dailymotion': {'dailymotion.com', 'dai.ly'},
    'instagram': {'instagram.com'},
    'facebook': {'facebook.com', 'fb.watch'},
    'reddit': {'reddit.com', 'redd.it', 'redditmedia.com', 'v.redd.it'},
    'twitch': {'twitch.tv'},
    'soundcloud': {'soundcloud.com'},
    'rumble': {'rumble.com', 'rmbl.ws'},
    'bilibili': {'bilibili.com', 'bilibili.tv', 'b23.tv'},
    'xiaohongshu': {'xiaohongshu.com', 'xhslink.com'},
    'bluesky': {'bsky.app'},
    'rutube': {'rutube.ru'},
    'vk': {'vk.com', 'vkvideo.ru', 'vk.ru'},
}

def detect_platform(url):
    try:
        host = (urlparse(url).hostname or '').lower().rstrip('.')
    except (TypeError, ValueError):
        return 'generic'
    for platform, domains in PLATFORM_HOSTS.items():
        if any(host == domain or host.endswith('.' + domain) for domain in domains):
            return platform
    return 'generic'
