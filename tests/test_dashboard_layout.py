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

        css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text(
            encoding="utf-8"
        )
        # kolom grafik memakai minmax(0, 1fr): tanpa itu SVG melebar mengikuti
        # isinya dan kolom total ikut menyempit
        block = css[css.index(".chart-block") : css.index(".sum-card")]
        self.assertIn("minmax(0, 1fr)", block)

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
