# backend/fetchers/__init__.py
from .base import BaseFetcher
from .ytdlp import YtDlpFetcher
from .scraper import ScraperFetcher
from .youtube import YouTubeFetcher
from .invidious import InvidiousFetcher
from .rumble import RumbleFetcher
from .reddit import RedditFetcher
from .bilibili import BilibiliFetcher   # <-- new

__all__ = [
    'BaseFetcher',
    'YtDlpFetcher',
    'ScraperFetcher',
    'YouTubeFetcher',
    'InvidiousFetcher',
    'RumbleFetcher',
    'RedditFetcher',
    'BilibiliFetcher',
]