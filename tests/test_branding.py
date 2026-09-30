import unittest

from app import app


class AirNavBrandingTest(unittest.TestCase):
    def test_branding_present_on_auth_pages(self):
        client = app.test_client()
        for path in ["/login", "/register"]:
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("AIRNAV", html)
            self.assertIn("INDONESIA", html)
            self.assertIn("LOGOAIRNAVINDONESIALandscape.png", html)
            self.assertNotIn("LandscapePutih", html)


if __name__ == '__main__':
    unittest.main()
