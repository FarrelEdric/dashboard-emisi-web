import unittest
from pathlib import Path

from app import app


class DashboardLayoutTest(unittest.TestCase):
    def test_dashboard_has_clear_route_then_content_order(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user"] = "admin"

        response = client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('class="route-panel card"', html)
        self.assertIn('class="content-panel card"', html)
        self.assertIn('class="calc-panel"', html)
        self.assertIn('class="map-panel"', html)

        self.assertLess(html.index('route-panel'), html.index('content-panel'))
        self.assertLess(html.index('content-panel'), html.index('map-panel'))

    def test_dashboard_has_one_analysis_section_and_no_route_comparison(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user"] = "admin"

        response = client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # perbandingan antar rute sudah dihapus, hanya grafik bulanan yang tersisa
        self.assertEqual(html.count('class="analysis-section"'), 1)
        self.assertNotIn("Perbandingan antar rute", html)
        self.assertNotIn('id="cmp"', html)
        self.assertNotIn('id="tt"', html)
        self.assertIn('id="chart"', html)

    def test_chart_is_sized_by_css_not_by_the_viewbox(self):
        css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text(
            encoding="utf-8"
        )
        # tinggi grafik dipatok CSS supaya skala tidak berubah saat panel menyempit
        self.assertIn("#chart {", css)
        self.assertNotIn(".cmp", css)

    def test_totals_sit_left_of_the_chart(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user"] = "admin"

        response = client.get("/dashboard")
        html = response.get_data(as_text=True)
        # total CO2 dan total penghematan berada di kolom kiri, sebelum grafik
        self.assertIn('class="chart-block"', html)
        self.assertLess(html.index('class="summary"'), html.index('id="chart"'))
        self.assertIn('id="sum-co2"', html)
        self.assertIn('id="sum-idr"', html)

    def test_chart_viewbox_is_measured_not_hardcoded(self):
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # viewBox disetel dari ukuran kotak grafik: kalau dipatok 800x175 lagi,
        # gambar menyusut dan menyisakan ruang kosong di kanan pada layar lebar
        self.assertIn('svg.setAttribute("viewBox", `0 0 ${w} ${h}`)', js)
        self.assertIn("svg.parentElement.clientWidth", js)

    def test_dashboard_handles_airports_without_routes(self):
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # dengan 242 bandara, sebagian besar belum punya rute: find() mengembalikan
        # undefined dan dulu load() langsung membaca r[2] sehingga UI melempar galat
        self.assertIn("if (!r) {", js)
        self.assertIn("if (!sel) {", js)
        # jangan lagi memulai dari rute tetap yang bisa saja tidak ada datanya
        self.assertNotIn('pick("CGK", "DPS")', js)

    def test_map_draws_only_the_selected_route(self):
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # garis abu-abu untuk seluruh rute lain dihapus: dengan ratusan bandara
        # garisnya memenuhi peta. Hanya rute terpilih yang digambar.
        self.assertNotIn("#94a3b8", js)
        self.assertNotIn("R.filter((r) => r !== sel)", js)
        self.assertIn('{ color: "#1060a8", weight: 3.5 }', js)

    def test_map_airport_dots_can_be_toggled(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user"] = "admin"

        html = client.get("/dashboard").get_data(as_text=True)
        # tombol geser untuk menyembunyikan titik bandara, aktif secara bawaan
        self.assertIn('id="ap-toggle"', html)
        self.assertIn('type="checkbox"', html)
        self.assertIn('class="switch"', html)
        self.assertIn('for="ap-toggle"', html)
        self.assertIn("checked", html)

        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # menggambar titik dipisah supaya tombol tidak perlu menghitung ulang emisi
        self.assertIn("function drawAirports(", js)
        self.assertIn("if (!dots) return;", js)
        self.assertIn("drawAirports(a, b);", js)
        self.assertIn('$("ap-toggle").onchange', js)
        self.assertIn("dots = e.target.checked;", js)

    def test_map_uses_a_free_tile_api_not_local_geometry(self):
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # gaya peta dari berkas lokal, ubinnya dari API OpenFreeMap (gratis,
        # tanpa kunci, boleh komersial)
        self.assertIn('"/static/style/map-natural.json"', js)
        self.assertIn("L.maplibreGL(", js)
        # kredit wajib ikut tampil
        self.assertIn("openfreemap.org", js)
        self.assertIn("openstreetmap.org/copyright", js)
        # geometri peta buatan sendiri sudah tidak dipakai
        self.assertNotIn("indonesia-land.geojson", js)
        self.assertNotIn("loadLabels", js)

    def test_map_style_is_a_natural_bright_copy_of_openfreemap(self):
        """Gaya peta disimpan sebagai berkas, bukan diambil jadi dari penyedia."""
        import json

        root = Path(__file__).resolve().parent.parent
        style = json.loads(
            (root / "static" / "style" / "map-natural.json").read_text(encoding="utf-8")
        )
        self.assertTrue(style["layers"], "gaya peta tanpa lapisan")
        # ubin tetap dari OpenFreeMap: yang dipakai adalah penyedianya, berkasnya
        # hanya salinan gaya supaya tampilannya ikut di-commit
        blob = json.dumps(style)
        self.assertIn("tiles.openfreemap.org", blob)
        # glyph dan sprite ikut menunjuk ke sana, kalau tidak nama tempat hilang
        self.assertIn("tiles.openfreemap.org/fonts/", style["glyphs"])
        self.assertIn("tiles.openfreemap.org/sprites/", style["sprite"])
        # tampilan peta natural: laut biru muda, daratan krem
        water = next(l for l in style["layers"] if l["id"] == "water")
        self.assertEqual(water["paint"]["fill-color"], "#AECFE2")
        background = next(l for l in style["layers"] if l["id"] == "background")
        self.assertEqual(background["paint"]["background-color"], "#f8f4f0")
        # nama tempat ditulis gelap berhalo putih, bukan putih berhalo gelap —
        # itulah yang membuat petanya terbaca seperti peta pada umumnya
        city = next(l for l in style["layers"] if l["id"] == "label_city")
        self.assertEqual(city["paint"]["text-color"], "#000")
        self.assertEqual(city["paint"]["text-halo-color"], "#fff")
        # palet gelap yang lama sudah tidak dipakai
        for dark in ("#34545c", "#5c6058", "#2b3338"):
            self.assertNotIn(dark, blob, f"palet gelap {dark} masih terpakai")
        # setiap properti paint harus dikenal jenis lapisannya; satu properti
        # asing membuat MapLibre menolak seluruh gaya dan peta tampil kosong
        allowed = {
            "background": ("background-",),
            "fill": ("fill-",),
            "line": ("line-",),
            "symbol": ("text-", "icon-"),
            "raster": ("raster-",),
            "fill-extrusion": ("fill-extrusion-",),
        }
        for layer in style["layers"]:
            prefixes = allowed.get(layer["type"])
            if prefixes is None:
                continue
            for key in layer.get("paint") or {}:
                self.assertTrue(
                    any(key.startswith(p) for p in prefixes),
                    f'{layer["id"]} ({layer["type"]}) memakai properti {key}',
                )

    def test_map_looks_and_behaves_like_a_map(self):
        """Peta harus bisa digeser/di-zoom seperti peta pada umumnya."""
        root = Path(__file__).resolve().parent.parent
        js = (root / "static" / "app.js").read_text(encoding="utf-8")

        # rentang zoom cukup lebar: z3 untuk konteks wilayah, z12 untuk satu kota
        self.assertIn("map.options.minZoom = 3", js)
        self.assertIn("map.options.maxZoom = 12", js)
        # zoom setengah langkah supaya peta bisa pas mengikuti panjang rute
        self.assertIn("zoomSnap: 0.5", js)
        # rute diberi garis putih di bawahnya supaya terbaca di atas peta
        self.assertIn('{ color: "#ffffff", weight: 7', js)

    def test_only_selected_airports_are_labelled(self):
        """242 nama bandara sekaligus membuat peta penuh tulisan."""
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function labelSpot(", js)
        # label tetap hanya untuk bandara asal & tujuan; sisanya lewat hover
        self.assertIn("if (h) {", js)
        self.assertIn("permanent: true", js)

    def test_totals_are_formatted_in_rupiah(self):
        js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        # nilai rupiah penuh dan bentuk pendek (miliar/triliun) untuk kartu total
        self.assertIn('const rpShort = (n) =>', js)
        self.assertIn("miliar", js)
        self.assertIn('$("sum-idr").textContent = rpShort(tt.idr)', js)
        self.assertIn('$("sum-co2").textContent = tons(tt.co2 / 1000)', js)
        # asumsi biaya ikut memperbarui total rupiah
        self.assertIn('if (i === "ci" || i === "fx") summary();', js)


if __name__ == '__main__':
    unittest.main()
