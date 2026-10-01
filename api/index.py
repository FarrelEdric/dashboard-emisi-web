"""Entrypoint untuk Vercel.

Vercel memanggil function ini, lalu semua request diarahkan ke sini lewat
rewrites. app.py di root tetap menjadi aplikasi sebenarnya; berkas ini hanya
menjembatani supaya Vercel menemukan instance Flask-nya.
"""
import os
import sys

# root proyek harus ada di sys.path agar `import app` bekerja di dalam function
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app import app  # noqa: E402  (objek WSGI yang dipakai Vercel)
