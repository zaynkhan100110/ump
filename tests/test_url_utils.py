import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))
from platform_detector import detect_platform
from utils import normalize_url, rumble_fallback_url, vimeo_fallback_url


class URLNormalizationTests(unittest.TestCase):
    def test_bilibili_bv_preserves_part_number(self):
        self.assertEqual(
            normalize_url('https://m.bilibili.com/video/BV1xx411c7mD/?p=2'),
            'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
        )

    def test_bilibili_av_is_supported(self):
        self.assertEqual(
            normalize_url('https://www.bilibili.com/video/av170001'),
            'https://www.bilibili.com/video/av170001',
        )

    def test_b23_short_link_is_left_for_official_redirect(self):
        self.assertEqual(normalize_url('https://b23.tv/AbCdEf'), 'https://b23.tv/AbCdEf')
        self.assertEqual(detect_platform('https://b23.tv/AbCdEf'), 'bilibili')

    def test_vimeo_share_fallback(self):
        self.assertEqual(
            vimeo_fallback_url('https://vimeo.com/1222049983?share=copy&fl=cl'),
            'https://player.vimeo.com/video/1222049983',
        )

    def test_vimeo_player_url_is_idempotent(self):
        self.assertEqual(
            vimeo_fallback_url('https://player.vimeo.com/video/1222049983'),
            'https://player.vimeo.com/video/1222049983',
        )

    def test_rumble_page_and_short_fallback(self):
        self.assertEqual(
            rumble_fallback_url('https://rumble.com/v7hm8wy-example.html'),
            'https://rumble.com/embed/v7hm8wy/',
        )
        self.assertEqual(
            rumble_fallback_url('https://rumble.com/shorts/v7diruq'),
            'https://rumble.com/embed/v7diruq/',
        )

    def test_invisible_format_characters_are_removed(self):
        self.assertEqual(normalize_url('\u200ehttps://b23.tv/AbCdEf\u200f'), 'https://b23.tv/AbCdEf')

    def test_untrusted_domain_substring_not_detected(self):
        self.assertEqual(detect_platform('https://notbilibili.com/video/BV1xx411c7mD'), 'generic')


if __name__ == '__main__':
    unittest.main()
