"""Salin data dari database lokal ke database online (Neon).

Dijalankan di KOMPUTERMU, bukan di server. Contoh:
    python copy_db.py                    # sumber: dashboard.db, tujuan: ditanyakan (tempel alamat Neon)
    python copy_db.py --users            # ikut menyalin akun pengguna biasa (admin tidak ikut)
    python copy_db.py --source "mysql+pymysql://root:@localhost:3306/emisi_karbon"

Yang disalin: bandara, rute, penerbangan per hari.
PERHATIAN: data bandara/rute/penerbangan di database tujuan DIGANTI dengan data dari sumber.
"""
import argparse
import ssl
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from models import Airport, Route, RouteFlight, User, db  # noqa: F401 (mendaftarkan tabel)

BASE = Path(__file__).parent
DATA_TABLES = ["airport", "route", "route_flight"]


def make_engine(raw):
    """Sama seperti pengaturan di app.py: driver pg8000, sslmode dibuang, SSL aktif untuk host online."""
    url, args = make_url(raw.strip()), {}
    if url.get_backend_name() in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+pg8000")
        url = url.set(query={k: v for k, v in url.query.items() if k not in ("sslmode", "channel_binding")})
        if url.host not in (None, "localhost", "127.0.0.1"):
            args["ssl_context"] = ssl.create_default_context()
    return create_engine(url, connect_args=args, pool_pre_ping=True)


def count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="alamat database sumber (bawaan: dashboard.db di folder ini)")
    p.add_argument("--target", help="alamat database tujuan (kalau kosong, akan ditanyakan)")
    p.add_argument("--users", action="store_true", help="ikut salin akun pengguna biasa (bukan admin)")
    p.add_argument("--yes", action="store_true", help="lewati pertanyaan konfirmasi")
    a = p.parse_args()

    source_url = a.source or "sqlite:///" + str(BASE / "dashboard.db")
    target_url = a.target or input("Tempel alamat database tujuan (Neon), lalu Enter: ")
    if not target_url.strip():
        raise SystemExit("Alamat tujuan kosong.")
    src, tgt = make_engine(source_url), make_engine(target_url)

    tables = {t.name: t for t in db.metadata.sorted_tables}
    ordered = [tables[n] for n in DATA_TABLES]  # airport -> route -> route_flight (urutan aman untuk relasi)
    db.metadata.create_all(tgt)  # buat tabel di tujuan kalau belum ada

    with src.connect() as s, tgt.connect() as t:
        if count(s, tables["airport"]) == 0:
            raise SystemExit("Database sumber kosong. Isi dulu datanya (jalankan python app.py lalu buka /admin).")
        print("\nSUMBER -> TUJUAN")
        for tb in ordered:
            print(f"  {tb.name:<13} sumber: {count(s, tb):>4} baris | tujuan sekarang: {count(t, tb):>4} baris (akan diganti)")
        if not a.yes and input("\nLanjut dan GANTI data di tujuan? Ketik 'ya' untuk lanjut: ").strip().lower() != "ya":
            raise SystemExit("Dibatalkan. Tidak ada yang diubah.")
        t.rollback()

    with src.connect() as s, tgt.begin() as t:  # begin() = semua-atau-tidak-sama-sekali
        for tb in reversed(ordered):
            t.execute(tb.delete())
        for tb in ordered:
            rows = [dict(r._mapping) for r in s.execute(select(tb))]
            if rows:
                t.execute(tb.insert(), rows)
            print(f"  disalin {tb.name}: {len(rows)} baris")
        if t.dialect.name == "postgresql":
            # id rute ikut disalin apa adanya, jadi penghitung id di PostgreSQL harus disusulkan
            t.execute(text("SELECT setval(pg_get_serial_sequence('route', 'id'), "
                           "(SELECT COALESCE(MAX(id), 1) FROM route), (SELECT COUNT(*) > 0 FROM route))"))
        if a.users:
            ut = tables["user"]
            have = {r[0].lower() for r in t.execute(select(ut.c.username))}
            added = skipped = 0
            for r in s.execute(select(ut)):
                m = dict(r._mapping)
                if m.get("role") == "admin" or m["username"].lower() in have:
                    skipped += 1
                    continue
                t.execute(ut.insert(), [m])
                added += 1
            print(f"  akun pengguna: {added} disalin, {skipped} dilewati (admin atau sudah ada)")
    print("\nSelesai. Buka website online dan muat ulang halamannya.")


if __name__ == "__main__":
    main()
