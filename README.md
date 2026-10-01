# Dashboard Emisi Karbon (Flask)

Website dengan login, pendaftaran akun (disetujui admin), dashboard emisi karbon, dan halaman admin untuk mengisi data.

## Isi proyek
- `app.py`: server Flask (login, daftar, dashboard, halaman admin, `/api/data`)
- `models.py`: tabel database (user, airport, route, route_flight)
- `importer.py`: data contoh awal + impor Excel/CSV + data bandara Indonesia
- `data/airports_id.csv`: 241 bandara Indonesia (kode IATA, nama, koordinat)
- `templates/`: login, register, dashboard, admin
- `static/`: style.css dan app.js
- `static/fonts/`, `static/img/`, `static/vendor/`, `static/style/`: aset lokal (lihat di bawah)
- `tools/build_map_style.py`: penyunting salinan gaya peta (dijalankan di komputer saja)
- `vercel.json`, `requirements.txt`, `Procfile`, `render.yaml`: pengaturan deploy

## Aset lokal (tanpa CDN)
Aset halaman disimpan di repo, jadi tampilan tidak bergantung layanan luar:

- `static/fonts/` — Exo 2 (5 berkas subset `.woff2`, variable font bobot 400-700, dari Google Fonts) beserta `exo2.css` yang mengarah ke berkas lokal.
- `static/vendor/leaflet/` — Leaflet 1.9.4 (`leaflet.js`, `leaflet.css`, `images/`).
- `static/vendor/maplibre/` — MapLibre GL JS 5.9.0 + `maplibre-gl.css` + `leaflet-maplibre-gl.js`.
- `static/img/logo-airnav.png` — logo AirNav Indonesia.
- `static/img/favicon.png` — ikon tab.
- `static/style/map-natural.json` — gaya peta (aturan warna) untuk MapLibre.

## Peta
Latar peta memakai ubin vektor **OpenFreeMap** (`https://tiles.openfreemap.org`), penyedia peta yang bisa dipakai tanpa biaya:

- tanpa kunci API, tanpa pendaftaran;
- tanpa batas jumlah tampilan/permintaan ("no limits on the number of map views or requests");
- penggunaan komersial **boleh** ("Is commercial usage allowed? Yes.");
- datanya dari OpenStreetMap (ODbL).

Ubin vektornya dirender **MapLibre GL JS**, dipasang sebagai lapisan di dalam Leaflet (`leaflet-maplibre-gl`), jadi rute, titik bandara, label bandara, pesawat, dan tombol "Titik bandara" tetap memakai kode Leaflet yang sudah ada.

### Gaya peta (warna)
Gaya petanya gaya bawaan OpenFreeMap **`bright`**, disalin ke `static/style/map-natural.json` apa adanya (tidak ada warna yang disetel ulang). Tampilannya seperti peta pada umumnya:

| bagian | warna |
| --- | --- |
| laut, sungai | `#AECFE2`, `#a0c8f0` (biru) |
| daratan | `#f8f4f0` (krem) |
| hutan / taman / padang rumput | `#d8e8c8` hijau muda (hutan `#6a4` pada 10% kepekatan) |
| jalan tol / jalan besar / jalan kecil | `#fc8` / `#fea` / `#fff` bertepi `#e9ac77`–`#cfcdca` (oranye) |
| nama tempat | `#000`/`#333` dengan garis bayangan `#fff` |

Kenapa disalin, bukan langsung memakai URL gaya milik penyedia: isi berkas ini ikut di-commit, jadi tampilan peta tidak berubah sendiri kalau OpenFreeMap memperbarui gaya bawaannya.

Yang perlu diketahui soal berkas ini:

- **Ubin, glyph, dan sprite tetap diambil dari OpenFreeMap.** Berkasnya hanya menyalin *gaya* (aturan warna), bukan data petanya. Jadi kewajiban menampilkan kredit tetap berlaku.
- **Setiap properti warna harus cocok dengan jenis lapisannya.** Satu properti asing (mis. `line-color` pada lapisan `symbol`) membuat MapLibre menolak **seluruh** gaya dan petanya tampil kosong tanpa pesan — gejalanya sama seperti ubin gagal dimuat. Karena itu `tools/build_map_style.py` membuang properti yang tidak dikenal, dan ada tes yang memeriksanya.
- **Memperbarui salinannya lewat skrip, bukan tangan.** Jalankan:
  ```
  python -m tools.build_map_style
  ```
  Skrip itu mengunduh gaya `bright` terbaru dan menulis ulang `static/style/map-natural.json`. Skrip hanya dijalankan di komputer (butuh internet); berkas JSON hasilnya ikut di-commit karena dibaca langsung oleh halaman. Ingin warna lain? Sunting palet di dalam berkasnya (atau tambahkan penyetelan warna di skrip) lalu jalankan ulang.

Kredit wajib tampil di pojok peta: `© OpenFreeMap · data © OpenStreetMap contributors`. Jangan dihilangkan — itu syarat pemakaian gratisnya.

Catatan pembanding (diperiksa langsung, bukan dari bacaan): CARTO, Stadia, MapTiler, dan Thunderforest juga gratis tapi **wajib kunci API** (CARTO membatasi 5 juta permintaan ubin/bulan), sedangkan `tile.openstreetmap.org` menolak dengan `HTTP 200` + header `x-blocked` dan ubinnya berisi tulisan "Access blocked" — tile OSM tidak boleh diambil massal atau dipakai untuk aplikasi pihak ketiga.

## Peran pengguna
- **admin**: dibuat dari `ADMIN_USER` dan `ADMIN_PASSWORD`. Bisa membuka halaman Admin.
- **user**: mendaftar lewat halaman Daftar. Baru bisa masuk setelah admin menyetujui.

## Jalankan di komputer
```
python -m pip install -r requirements.txt
python app.py
```
File `.env` berisi `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`. `DATABASE_URL` dikosongkan supaya memakai SQLite (`dashboard.db`) di komputer.

## Halaman Admin (`/admin`)
- **Pengguna**: setujui atau tolak akun baru.
- **Unggah data**: Excel (.xlsx, format sheet RNAV) atau CSV, per tahun dan triwulan.
- **Bandara, Rute, Penerbangan per hari**: tambah atau ubah lewat formulir.
- **Data saat ini**: lihat isi database per tahun, hapus rute.

Format CSV: header `rute,hemat_nm,hemat_menit,penerbangan_per_hari`, contoh isi `CGK-DPS,12.1,1.7,50` (pemisah koma atau titik koma). Contoh file bisa diunduh dari halaman Admin.

## Database
- Di komputer: SQLite (`dashboard.db`), otomatis dibuat dan diisi data contoh.
- Online: isi `DATABASE_URL` dengan alamat PostgreSQL (Neon). Website online dan komputermu memakai database yang terpisah.
- Tabel `user` lama otomatis ditambah kolom `role` dan `approved` saat aplikasi menyala.

## Data bandara Indonesia
`data/airports_id.csv` berisi 241 bandara Indonesia (kode IATA + nama + koordinat), hasil saringan dari data OurAirports. Saat aplikasi menyala, `ensure_airports()` menambahkan bandara yang **belum ada** di database — hanya menambah, tidak pernah mengubah atau menghapus. Bandara yang sudah ada (termasuk CGK dan HLM yang koordinatnya dirapikan manual) dibiarkan apa adanya.

- Database baru: 7 bandara contoh dari `data.json` + 235 bandara dari CSV = 242 bandara.
- Bandara tanpa data rute tetap muncul di pemilih; dashboard menampilkan "Belum ada data rute untuk XXX" dan rutenya ditambahkan lewat halaman Admin.
- Kolom `dx`, `dy`, `anchor` (geser label di peta) memakai nilai bawaan; ubah per bandara jika labelnya bertumpuk.
- Menambah bandara lagi: tambahkan baris ke `data/airports_id.csv` (kolom `code,name,lat,lon`), lalu jalankan aplikasi lagi.

## Memindahkan data lokal ke Neon
Isi data dulu di komputer (`python app.py`, login, buka `/admin`), lalu jalankan di komputer (venv aktif):
```
python copy_db.py
```
Tempel alamat Neon saat diminta, lalu ketik `ya`. Bandara, rute, dan penerbangan per hari di Neon DIGANTI dengan data lokal. Tambahkan `--users` untuk ikut menyalin akun pengguna biasa (akun admin tidak pernah ikut disalin). File `copy_db.py` hanya dipakai di komputer.

## Deploy ke Vercel + Neon
Environment Variables di Vercel: `DATABASE_URL` (alamat Neon, tanpa spasi/enter di akhir), `ADMIN_USER`, `ADMIN_PASSWORD`, `SECRET_KEY`, `COOKIE_SECURE=1`.
Semua file di repo harus ada di **folder paling atas** (sejajar `app.py`), termasuk folder `templates` dan `static`.

## Catatan
- Pembatas percobaan login/daftar disimpan di memori server, jadi di Vercel kurang efektif (tiap instance punya catatan sendiri).
- Website ini hanya menampilkan data. Angka hasil hitungan tidak disimpan, dihitung ulang di dashboard.
- Tombol **Titik bandara** di bawah peta menyembunyikan/menampilkan titik seluruh bandara; rute terpilih tetap tergambar. Pengaturan ini hanya berlaku selama halaman terbuka, tidak disimpan di database.
