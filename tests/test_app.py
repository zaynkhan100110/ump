import os, tempfile, unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ['UMP_SECRET_KEY'] = 'test-secret-key-that-is-at-least-32-characters-long'
os.environ['UMP_COOKIE_SECURE'] = '0'
os.environ['UMP_DOWNLOAD_DIR'] = _tmp.name
os.environ['UMP_DATABASE_PATH'] = str(Path(_tmp.name) / 'test.sqlite3')
os.environ['UMP_ALLOW_REGISTRATION'] = '1'
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app as ump

class UMPApiTests(unittest.TestCase):
    def setUp(self):
        self.client = ump.app.test_client()
        with ump.db() as c:
            c.execute('DELETE FROM jobs')
            c.execute('DELETE FROM users')

    def register(self, username):
        return self.client.post('/api/auth/register', json={'username': username, 'password': 'correct-horse-battery-staple'})

    def test_health_is_public(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)

    def test_register_and_me(self):
        response = self.register('tester')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.client.get('/api/auth/me').json['authenticated'])

    def test_authenticated_mutation_requires_csrf(self):
        self.register('csrfuser')
        response = self.client.post('/api/download', json={'url':'https://example.com/video','format_id':'best'})
        self.assertEqual(response.status_code, 403)

    def test_url_rejects_localhost(self):
        with self.assertRaises(ValueError):
            ump.validate_url('http://127.0.0.1/admin')

    def test_url_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            ump.validate_url('file:///etc/passwd')

    def test_url_removes_invisible_unicode_format_characters(self):
        cleaned = ump.normalize_url('\u200ehttps://example.com/video\u200f')
        self.assertEqual(cleaned, 'https://example.com/video')


    def test_bilibili_bv_url_normalization_preserves_part(self):
        self.assertEqual(ump.normalize_url('https://m.bilibili.com/video/BV1xx411c7mD/?p=2'),
                         'https://www.bilibili.com/video/BV1xx411c7mD?p=2')

    def test_bilibili_av_url_normalization(self):
        self.assertEqual(ump.normalize_url('https://www.bilibili.com/video/av170001'),
                         'https://www.bilibili.com/video/av170001')

    def test_bilibili_short_link_is_preserved_for_official_redirect(self):
        self.assertEqual(ump.normalize_url('https://b23.tv/AbCdEf'), 'https://b23.tv/AbCdEf')

    def test_vimeo_player_fallback_is_generated(self):
        from utils import vimeo_fallback_url
        self.assertEqual(vimeo_fallback_url('https://vimeo.com/1222049983?share=copy'),
                         'https://player.vimeo.com/video/1222049983')

    def test_rumble_embed_fallback_is_generated(self):
        from utils import rumble_fallback_url
        self.assertEqual(rumble_fallback_url('https://rumble.com/v7hm8wy-example.html'),
                         'https://rumble.com/embed/v7hm8wy/')

    def test_platform_detector_recognizes_bilibili_short_links(self):
        from platform_detector import detect_platform
        self.assertEqual(detect_platform('https://b23.tv/AbCdEf'), 'bilibili')

    def test_platform_detector_recognizes_x_and_rejects_domain_substrings(self):
        from platform_detector import detect_platform
        self.assertEqual(detect_platform('https://x.com/meme_basement/status/123'), 'twitter')
        self.assertEqual(detect_platform('https://notyoutube.com/video'), 'generic')

if __name__ == '__main__':
    unittest.main()
