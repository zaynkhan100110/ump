"""Cross-platform URL cleanup and media URL recognition helpers."""
import re
import unicodedata
from urllib.parse import urlparse, parse_qs
from platform_detector import detect_platform

_URL_RE = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)
_BVID_RE = re.compile(r'(?i)(?:/video/)?(BV[0-9A-Za-z]{10})')
_AVID_RE = re.compile(r'(?i)(?:/video/)?av(\d{1,20})')
_RUMBLE_RE = re.compile(r'rumble\.com/(?:embed/|shorts/)?(v[0-9a-z]{5,})', re.I)
_VIMEO_RE = re.compile(r'(?:vimeo\.com/(?:video/)?|player\.vimeo\.com/video/)(\d{6,})', re.I)

def clean_pasted_text(value):
    if not isinstance(value, str):
        return ''
    return ''.join(ch for ch in value.strip() if unicodedata.category(ch) != 'Cf' and ch != '\ufeff').strip()

def normalize_url(value):
    """Clean common copied URLs without destroying query strings or page IDs."""
    value = clean_pasted_text(value)
    if not value or len(value) > 4096:
        return None
    match = _URL_RE.search(value)
    if match:
        value = match.group(0).rstrip('.,);]')
    elif re.match(r'^(?:[a-z0-9-]+\.)*(?:bilibili\.com|b23\.tv|vimeo\.com|rumble\.com|reddit\.com|youtu\.be|youtube\.com)/', value, re.I):
        value = 'https://' + value
    else:
        return value
    try:
        parsed = urlparse(value)
    except ValueError:
        return value
    platform = detect_platform(value)
    if platform == 'bilibili':
        # Normalize mobile/www and legacy av links, but leave b23.tv intact so yt-dlp
        # can follow the official short-link redirect. Preserve the selected part.
        if parsed.hostname and parsed.hostname.lower().endswith('bilibili.com'):
            bvid = _BVID_RE.search(parsed.path)
            avid = _AVID_RE.search(parsed.path)
            if bvid:
                part = parse_qs(parsed.query).get('p', [None])[0]
                suffix = f'?p={part}' if part and part.isdigit() else ''
                return f'https://www.bilibili.com/video/{bvid.group(1)}{suffix}'
            if avid:
                part = parse_qs(parsed.query).get('p', [None])[0]
                suffix = f'?p={part}' if part and part.isdigit() else ''
                return f'https://www.bilibili.com/video/av{avid.group(1)}{suffix}'
    if platform == 'rumble':
        # Keep the canonical page first; the extractor fallback layer may try embed IDs.
        return value
    return value

def rumble_fallback_url(url):
    match = _RUMBLE_RE.search(url)
    if not match:
        # Rumble page IDs have a v-prefix followed by alphanumerics.
        match = re.search(r'rumble\.com/(v[0-9a-z]+)(?:-[^/?#]*)?', url, re.I)
    if not match:
        return None
    video_id = match.group(1)
    if not video_id.lower().startswith('v'):
        video_id = 'v' + video_id
    return f'https://rumble.com/embed/{video_id}/'

def vimeo_fallback_url(url):
    match = _VIMEO_RE.search(url)
    if not match:
        return None
    return f'https://player.vimeo.com/video/{match.group(1)}'

def is_direct_video_url(url):
    return bool(re.search(r'\.(?:mp4|webm|mkv|avi|mov|flv|m4v|mp3|m4a|aac|ogg|wav|m3u8|mpd)(?:$|[?#])|/video\.php\?|/get_video\?|/v\.redd\.it/', url, re.I))
