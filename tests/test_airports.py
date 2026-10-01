import csv
import unittest
from pathlib import Path

from app import app
from importer import AIRPORT_CSV
from models import Airport, Route

ROOT = Path(__file__).resolve().parent.parent


class IndonesiaAirportsTest(unittest.TestCase):
    def test_airport_file_covers_indonesia_and_is_sane(self):
        self.assertTrue(AIRPORT_CSV.exists(), f"{AIRPORT_CSV} tidak ada")
        with AIRPORT_CSV.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        self.assertGreater(len(rows), 200, "data bandara Indonesia terlalu sedikit")
        codes = [r["code"] for r in rows]
        self.assertEqual(len(codes), len(set(codes)), "ada kode bandara ganda")

        for r in rows:
            self.assertRegex(r["code"], r"^[A-Z]{3}$")
            self.assertTrue(r["name"].strip(), f'{r["code"]} tanpa nama')
            self.assertLessEqual(len(r["name"]), 120, f'{r["code"]} namanya terlalu panjang')
            lat, lon = float(r["lat"]), float(r["lon"])
            # seluruh Indonesia: lintang -11,5..6,5 dan bujur 94,5..141,5
            self.assertTrue(-11.5 < lat < 6.5, f'{r["code"]} lintang di luar Indonesia: {lat}')
            self.assertTrue(94.5 < lon < 141.5, f'{r["code"]} bujur di luar Indonesia: {lon}')

        # bandara besar yang pasti dilayani harus ikut
        for code in ("CGK", "DPS", "SUB", "KNO", "UPG", "LOP", "YIA", "AMQ", "BIK", "TIM"):
            self.assertIn(code, codes, f"{code} tidak ada di data bandara Indonesia")

    def test_airport_file_has_no_duplicates_against_existing_names(self):
        # nama bandara lama (dari data.json) tidak boleh ikut lagi di CSV,
        # supaya seed tidak menimpa data yang sudah dirapikan
        with AIRPORT_CSV.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        csv_names = {r["name"] for r in rows}
        self.assertNotIn("Soekarno-Hatta, Jakarta", csv_names)
        self.assertNotIn("Halim Perdanakusuma, Jakarta", csv_names)

    def test_api_serves_airports_beyond_the_seeded_seven(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user"] = "admin"

        response = client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        airports = response.get_json()["airports"]
        self.assertGreaterEqual(len(airports), 100, "bandara Indonesia belum masuk")

        # bandara di luar Jawa juga ada, bukan hanya yang lama
        for code in ("KNO", "BIK", "TIM", "LOP", "AMQ"):
            self.assertIn(code, airports, f"{code} tidak ada di /api/data")
            name, lat, lon = airports[code][0], airports[code][1], airports[code][2]
            self.assertTrue(name.strip())
            self.assertTrue(-11.5 < lat < 6.5 and 94.5 < lon < 141.5, f"{code} koordinat aneh")

    def test_ensure_airports_only_adds_and_is_idempotent(self):
        with app.app_context():
            before = {a.code for a in Airport.query.all()}
            routes_before = Route.query.count()
            from importer import ensure_airports

            added_first = ensure_airports()  # semua harus sudah ada
            self.assertEqual(added_first, 0, "ensure_airports() menambah ulang bandara yang ada")
            self.assertEqual(ensure_airports(), 0, "ensure_airports() tidak idempoten")

            after = {a.code for a in Airport.query.all()}
            self.assertEqual(before, after, "kumpulan bandara berubah")
            self.assertEqual(Route.query.count(), routes_before, "rute ikut berubah")


if __name__ == "__main__":
    unittest.main()
