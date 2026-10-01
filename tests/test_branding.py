import unittest

from app import app


class AirNavBrandingTest(unittest.TestCase):
    def test_branding_present_on_auth_pages(self):
        client = app.test_client()
        for path in ["/login", "/register"]:
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            # logo sekarang berkas lokal, bukan gambar dari situs AirNav
            self.assertIn("AirNav Indonesia", html)
            self.assertIn("/static/img/logo-airnav.png", html)
            self.assertNotIn("LandscapePutih", html)

    def test_assets_are_served_locally(self):
        """Tidak ada aset yang diambil dari CDN atau situs lain."""
        client = app.test_client()
        for path in ["/login", "/register", "/dashboard"]:
            html = client.get(path).get_data(as_text=True)
            # yang boleh tetap jarak-jauh hanya penyedia ubin peta: itu memang API
        # peta pihak ketiga (OpenFreeMap), bukan aset halaman
        for remote in ("https://fonts.googleapis", "fonts.gstatic.com", "cdnjs.cloudflare.com",
                           "tile.openstreetmap", "airnavindonesia.co.id"):
                self.assertNotIn(remote, html, f"{path} masih memakai {remote}")

        # berkas lokal yang dirujuk benar-benar ada dan bisa disajikan
        for asset in ("/static/fonts/exo2.css", "/static/fonts/Exo2-latin.woff2",
                      "/static/img/logo-airnav.png", "/static/vendor/leaflet/leaflet.js",
                      "/static/vendor/leaflet/leaflet.css", "/static/vendor/leaflet/images/marker-icon.png",
                      "/static/vendor/maplibre/maplibre-gl.js",
                      "/static/vendor/maplibre/maplibre-gl.css",
                      "/static/vendor/maplibre/leaflet-maplibre-gl.js",
                      "/static/style/map-natural.json"):
            response = client.get(asset)
            try:
                self.assertEqual(response.status_code, 200, f"{asset} tidak bisa diakses")
                self.assertGreater(len(response.get_data()), 0, f"{asset} kosong")
            finally:
                response.close()

    def test_font_css_points_at_local_files_only(self):
        from pathlib import Path

        css = (Path(__file__).resolve().parent.parent / "static" / "fonts" / "exo2.css").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("https://", css)
        self.assertIn("Exo2-latin.woff2", css)
        self.assertIn("font-weight: 400 700", css)  # variable font
        self.assertIn("unicode-range", css)


if __name__ == '__main__':
    unittest.main()
