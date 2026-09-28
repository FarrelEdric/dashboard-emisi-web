import hmac
import io
import os
import re
import secrets
import ssl
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from sqlalchemy import func, inspect, text
from sqlalchemy.engine import make_url
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from importer import TEMPLATE_CSV, import_csv, import_excel, seed_if_empty
from models import Airport, Route, RouteFlight, User, db

load_dotenv()  # baca file .env saat dijalankan di komputer sendiri
BASE = Path(__file__).parent


def database_config():
    """Tentukan database. Kosong = SQLite di komputer. Isi DATABASE_URL = database online (Neon dll)."""
    raw = (os.environ.get("DATABASE_URL") or "").strip()  # strip: buang spasi/enter yang ikut tersalin
    if not raw:
        return "sqlite:///" + str(BASE / "dashboard.db"), {}
    url, args = make_url(raw), {}
    if url.get_backend_name() in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+pg8000")  # driver murni Python, cocok untuk Vercel
        # pg8000 tidak mengenal sslmode/channel_binding: buang dari alamat, SSL diatur di bawah
        url = url.set(query={k: v for k, v in url.query.items() if k not in ("sslmode", "channel_binding")})
        if url.host not in (None, "localhost", "127.0.0.1"):
            args["ssl_context"] = ssl.create_default_context()
    return url, args


DB_URL, DB_ARGS = database_config()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # agar IP asli terbaca di hosting
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-ganti-di-produksi"),
    SQLALCHEMY_DATABASE_URI=DB_URL,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "connect_args": DB_ARGS},
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",  # aktifkan di hosting (HTTPS)
    PERMANENT_SESSION_LIFETIME=8 * 3600,  # login berlaku 8 jam
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,   # unggahan maksimal 2 MB
)
db.init_app(app)


# ---------- Persiapan database ----------
def ensure_columns():
    """Tambah kolom baru ke tabel user yang sudah ada (create_all tidak mengubah tabel lama)."""
    cols = {c["name"] for c in inspect(db.engine).get_columns("user")}
    table = db.engine.dialect.identifier_preparer.quote("user")
    stmts = []
    if "role" not in cols:
        stmts.append(f"ALTER TABLE {table} ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'user'")
    if "approved" not in cols:
        stmts.append(f"ALTER TABLE {table} ADD COLUMN approved INTEGER NOT NULL DEFAULT 0")
    for stmt in stmts:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception:  # kolom sudah dibuat oleh proses lain yang jalan bersamaan
            db.session.rollback()


def ensure_admin():
    """Pastikan akun admin dari ADMIN_USER sudah ada."""
    user = os.environ.get("ADMIN_USER", "").strip()

    if not user:
        print("[login] PERINGATAN: ADMIN_USER tidak terbaca")
        return

    row = db.session.get(User, user)

    if row:
        print(f"[login] akun admin sudah ada: {user}")
        return

    pw = os.environ.get("ADMIN_PASSWORD", "")

    if not pw:
        print("[login] PERINGATAN: ADMIN_PASSWORD tidak terbaca")
        return

    db.session.add(
        User(
            username=user,
            password_hash=generate_password_hash(pw),
            role="admin",
            approved=1
        )
    )
    db.session.commit()

    print(f"[login] akun admin dibuat: {user}")

# ---------- Keamanan ----------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf"] = csrf_token


def check_csrf():
    token = session.get("csrf")
    if not token or not hmac.compare_digest(request.form.get("csrf", ""), token):
        abort(400)


ATTEMPTS = {}  # (jenis, ip) -> waktu percobaan. Catatan: di serverless tiap instance punya catatan sendiri.


def too_many(kind, ip, limit=5):
    key = (kind, ip)
    recent = [t for t in ATTEMPTS.get(key, []) if time.time() - t < 300]
    ATTEMPTS[key] = recent
    return len(recent) >= limit  # maksimal 5 kali per 5 menit


def note(kind, ip):
    ATTEMPTS.setdefault((kind, ip), []).append(time.time())


def find_user(name):
    return User.query.filter(func.lower(User.username) == name.strip().lower()).first()


def current_user():
    """Pengguna yang sedang login, dibaca dari database (jadi akun yang dihapus langsung tidak berlaku)."""
    if "cu" not in g:
        name = session.get("user")
        u = db.session.get(User, name) if name else None
        if name and (not u or not u.approved):
            session.pop("user", None)
            u = None
        g.cu = u
    return g.cu


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify(error="unauthorized"), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        if u.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@app.after_request
def no_cache(resp):
    if not request.path.startswith("/static"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- Halaman umum ----------
@app.route("/")
def index():
    return redirect(url_for("dashboard" if current_user() else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        check_csrf()
        ip = request.remote_addr
        if too_many("login", ip):
            error = "Terlalu banyak percobaan. Coba lagi 5 menit lagi."
        else:
            row = find_user(request.form.get("username", ""))
            if row and check_password_hash(row.password_hash, request.form.get("password", "")):
                if not row.approved:
                    error = "Akunmu belum disetujui admin. Coba lagi setelah disetujui."
                else:
                    session.clear()
                    session["user"] = row.username
                    session.permanent = True
                    return redirect(url_for("dashboard"))
            else:
                note("login", ip)
                error = "Username atau password salah."
    return render_template("login.html", error=error), (401 if error else 200)


USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        check_csrf()
        ip = request.remote_addr
        username = request.form.get("username", "").strip()
        pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
        if too_many("register", ip):
            error = "Terlalu banyak percobaan. Coba lagi 5 menit lagi."
        else:
            note("register", ip)
            if not USERNAME_RE.fullmatch(username):
                error = "Username 3-30 karakter: huruf, angka, atau garis bawah."
            elif len(pw) < 8:
                error = "Password minimal 8 karakter."
            elif pw != pw2:
                error = "Konfirmasi password tidak sama."
            elif find_user(username):
                error = "Username sudah dipakai."
            else:
                db.session.add(User(username=username.lower(), password_hash=generate_password_hash(pw),
                                    role="user", approved=0))
                db.session.commit()
                flash("Akun dibuat. Tunggu admin menyetujui, setelah itu kamu bisa masuk.")
                return redirect(url_for("login"))
    return render_template("register.html", error=error), (400 if error else 200)


@app.post("/logout")
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    return render_template("dashboard.html", username=u.username, is_admin=u.role == "admin")


def flights_by_route(year):
    out = {}
    for f in RouteFlight.query.filter_by(year=year):
        out.setdefault(f.route_id, [0, 0, 0, 0])[f.quarter - 1] = f.flights_per_day
    return out


@app.route("/api/data")
@login_required
def data():
    """Data dashboard dari database untuk tahun yang dipilih (?year=2026)."""
    years = sorted({y for (y,) in db.session.query(RouteFlight.year).distinct()})
    year = request.args.get("year", type=int) or (years[-1] if years else 2026)
    airports = {a.code: [a.name, a.lat, a.lon, a.dx, a.dy, a.anchor] for a in Airport.query}
    flights = flights_by_route(year)
    routes = [[r.origin, r.dest, r.saving_nm, r.saving_min, flights.get(r.id, [0, 0, 0, 0])]
              for r in Route.query.order_by(Route.id)]
    return jsonify(airports=airports, routes=routes, years=years or [year])


# ---------- Halaman admin ----------
def number(field, label, low, high):
    try:
        value = float(request.form.get(field, "").strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{label} harus berupa angka.")
    if not low <= value <= high:
        raise ValueError(f"{label} harus antara {low:g} dan {high:g}.")
    return value


def whole(field, label, low, high):
    return int(number(field, label, low, high))


def back():
    return redirect(url_for("admin", year=request.form.get("view_year", type=int) or None))


@app.route("/admin")
@admin_required
def admin():
    year = request.args.get("year", type=int) or 2026
    routes = Route.query.order_by(Route.origin, Route.dest).all()
    return render_template(
        "admin.html", me=current_user().username, year=year, routes=routes,
        users=User.query.order_by(User.approved, User.username).all(),
        airports=Airport.query.order_by(Airport.code).all(),
        flights=flights_by_route(year),
    )


@app.post("/admin/user/<username>/approve")
@admin_required
def admin_approve(username):
    check_csrf()
    u = db.session.get(User, username)
    if u:
        u.approved = 1
        db.session.commit()
        flash(f"Akun {u.username} disetujui.")
    return back()


@app.post("/admin/user/<username>/delete")
@admin_required
def admin_delete_user(username):
    check_csrf()
    u = db.session.get(User, username)
    if not u:
        pass
    elif u.role == "admin":
        flash("Akun admin tidak bisa dihapus dari sini.", "error")
    else:
        db.session.delete(u)
        db.session.commit()
        flash(f"Akun {username} dihapus.")
    return back()


@app.post("/admin/airport")
@admin_required
def admin_airport():
    check_csrf()
    try:
        code = request.form.get("code", "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise ValueError("Kode bandara harus 3 huruf, contoh CGK.")
        name = request.form.get("name", "").strip()
        if not name or len(name) > 120:
            raise ValueError("Nama bandara wajib diisi (maksimal 120 huruf).")
        lat = number("lat", "Lintang", -90, 90)
        lon = number("lon", "Bujur", -180, 180)
        a = db.session.get(Airport, code)
        if a:
            a.name, a.lat, a.lon = name, lat, lon
        else:
            db.session.add(Airport(code=code, name=name, lat=lat, lon=lon))
        db.session.commit()
        flash(f"Bandara {code} disimpan.")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return back()


@app.post("/admin/route")
@admin_required
def admin_route():
    check_csrf()
    try:
        a, b = request.form.get("origin", ""), request.form.get("dest", "")
        if a == b:
            raise ValueError("Bandara asal dan tujuan harus berbeda.")
        if not (db.session.get(Airport, a) and db.session.get(Airport, b)):
            raise ValueError("Pilih bandara yang sudah terdaftar.")
        nm = number("saving_nm", "Hemat jarak (Nm)", 0, 500)
        mn = number("saving_min", "Hemat waktu (menit)", 0, 120)
        r = Route.query.filter(((Route.origin == a) & (Route.dest == b)) |
                               ((Route.origin == b) & (Route.dest == a))).first()
        if r:
            r.saving_nm, r.saving_min = nm, mn
        else:
            db.session.add(Route(origin=a, dest=b, saving_nm=nm, saving_min=mn))
        db.session.commit()
        flash(f"Rute {a}-{b} disimpan.")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return back()


@app.post("/admin/route/<int:route_id>/delete")
@admin_required
def admin_delete_route(route_id):
    check_csrf()
    r = db.session.get(Route, route_id)
    if r:
        RouteFlight.query.filter_by(route_id=route_id).delete()
        db.session.delete(r)
        db.session.commit()
        flash(f"Rute {r.origin}-{r.dest} dihapus.")
    return back()


@app.post("/admin/flights")
@admin_required
def admin_flights():
    check_csrf()
    try:
        route = db.session.get(Route, whole("route_id", "Rute", 1, 10**9))
        if not route:
            raise ValueError("Rute tidak ditemukan.")
        year, quarter = whole("year", "Tahun", 2020, 2100), whole("quarter", "Triwulan", 1, 4)
        flights = number("flights", "Penerbangan per hari", 0, 2000)
        rf = db.session.get(RouteFlight, (route.id, year, quarter))
        if rf:
            rf.flights_per_day = flights
        else:
            db.session.add(RouteFlight(route_id=route.id, year=year, quarter=quarter, flights_per_day=flights))
        db.session.commit()
        flash(f"{route.origin}-{route.dest}: {flights:g} penerbangan/hari untuk {year} TW {quarter} disimpan.")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return back()


@app.post("/admin/import")
@admin_required
def admin_import():
    check_csrf()
    try:
        year, quarter = whole("year", "Tahun", 2020, 2100), whole("quarter", "Triwulan", 1, 4)
        f = request.files.get("file")
        if not f or not f.filename:
            raise ValueError("Pilih file dulu.")
        name, raw = f.filename.lower(), f.read()
        if name.endswith(".xlsx"):
            count = import_excel(io.BytesIO(raw), year, quarter)
        elif name.endswith(".csv"):
            try:
                text_csv = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError("File CSV harus disimpan dengan encoding UTF-8.")
            count = import_csv(text_csv, year, quarter)
        else:
            raise ValueError("Format file harus .xlsx atau .csv.")
        if count == 0:
            raise ValueError("Tidak ada baris rute yang terbaca. Cek format kolomnya.")
        flash(f"{count} rute berhasil diimpor untuk {year} TW {quarter}.")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    except Exception:
        db.session.rollback()
        flash("File tidak bisa dibaca. Pastikan itu file .xlsx atau .csv yang benar.", "error")
    return back()


@app.route("/admin/template.csv")
@admin_required
def template_csv():
    return Response(TEMPLATE_CSV, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=template-rute.csv"})


if __name__ == "__main__":
    app.run(debug=True)  # hanya untuk di komputer sendiri
