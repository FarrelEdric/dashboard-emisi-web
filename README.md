# Dashboard Emisi Karbon (Flask)

Website dengan login, pendaftaran akun (disetujui admin), dashboard emisi karbon, dan halaman admin untuk mengisi data.

## Isi proyek
- `app.py`: server Flask (login, daftar, dashboard, halaman admin, `/api/data`)
- `models.py`: tabel database (user, airport, route, route_flight)
- `importer.py`: data contoh awal + impor Excel/CSV
- `templates/`: login, register, dashboard, admin
- `static/`: style.css dan app.js
- `vercel.json`, `requirements.txt`, `Procfile`, `render.yaml`: pengaturan deploy

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
