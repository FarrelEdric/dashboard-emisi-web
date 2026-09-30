import unittest

from app import app


class StaticCacheHeadersTest(unittest.TestCase):
    def test_static_assets_are_not_cached(self):
        client = app.test_client()
        response = client.get('/static/style.css')
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers.get('Cache-Control', '').lower())
        finally:
            response.close()


if __name__ == '__main__':
    unittest.main()
