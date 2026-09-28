from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user", server_default="user")  # "admin" atau "user"
    approved = db.Column(db.Integer, nullable=False, default=0, server_default="0")          # 1 = boleh login


class Airport(db.Model):
    code = db.Column(db.String(3), primary_key=True)  # kode IATA, mis. CGK
    name = db.Column(db.String(120), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    dx = db.Column(db.Integer, default=8)              # posisi label di peta
    dy = db.Column(db.Integer, default=-8)
    anchor = db.Column(db.String(10), default="start")


class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin = db.Column(db.String(3), db.ForeignKey("airport.code"), nullable=False)
    dest = db.Column(db.String(3), db.ForeignKey("airport.code"), nullable=False)
    saving_nm = db.Column(db.Float, nullable=False)    # hemat jarak (Nm)
    saving_min = db.Column(db.Float, nullable=False)   # hemat waktu (menit)
    __table_args__ = (db.UniqueConstraint("origin", "dest"),)


class RouteFlight(db.Model):
    """Penerbangan per hari untuk satu rute pada satu triwulan."""
    route_id = db.Column(db.Integer, db.ForeignKey("route.id"), primary_key=True)
    year = db.Column(db.Integer, primary_key=True)
    quarter = db.Column(db.Integer, primary_key=True)  # 1..4
    flights_per_day = db.Column(db.Float, nullable=False)
