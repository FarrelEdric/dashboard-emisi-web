"""Generate preview HTML of the real rendered pages, for visual QA only.

Not part of the app: writes _preview_*.html at the repo root, keeps app.js but
stubs its /api/data fetch with fixture data so the JS-built chart, map and
result boxes really render, and repoints the CSS. Serve over
http://localhost — never open the file directly with file://.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app  # noqa: E402

ROOT = Path(__file__).resolve().parent

# Optionally preview an alternative stylesheet:
#   python _make_preview.py scratch/style-broken.css broken
# Pass "live" as the first argument to embed the app's real /api/data response
# (every airport in the database) instead of the fixture below.
CSS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("static/style.css")
SUFFIX = f"_{sys.argv[2]}" if len(sys.argv) > 2 else ""
LIVE = CSS.as_posix() == "live"
if LIVE:
    CSS, SUFFIX = Path("static/style.css"), "_live"

# Fixture served in place of /api/data so the dashboard JS runs for real.
FIXTURE = {
    "airports": {
        "CGK": ["Soekarno-Hatta", -6.1256, 106.6558, 0, 0, "CGK"],
        "DPS": ["Ngurah Rai", -8.7482, 115.1672, 0, 0, "DPS"],
        "SUB": ["Juanda", -7.3798, 112.7869, 0, 0, "SUB"],
        "LBJ": ["Komodo", -8.4867, 119.8891, 0, 0, "LBJ"],
        "KNO": ["Kualanamu", 3.6378, 98.8853, 0, 0, "KNO"],
        "UPG": ["Sultan Hasanuddin", -5.0616, 119.5540, 0, 0, "UPG"],
        "BPN": ["Sultan Aji Muhammad Sulaiman", -1.2683, 116.8944, 0, 0, "BPN"],
        "MDC": ["Sam Ratulangi", 1.5492, 124.9264, 0, 0, "MDC"],
    },
    "routes": [
        ["CGK", "DPS", 670, 52, [5, 6, 7, 8]],
        ["CGK", "SUB", 420, 33, [8, 9, 9, 10]],
        ["CGK", "KNO", 510, 41, [4, 5, 5, 6]],
        ["CGK", "UPG", 480, 38, [3, 4, 4, 5]],
        ["CGK", "BPN", 430, 35, [2, 3, 3, 3]],
        ["CGK", "MDC", 720, 58, [2, 2, 3, 3]],
        ["DPS", "LBJ", 210, 17, [3, 3, 4, 4]],
        ["SUB", "UPG", 320, 26, [2, 3, 3, 4]],
        ["DPS", "UPG", 260, 21, [1, 2, 2, 2]],
    ],
    "years": [2025, 2026],
}


def preview(name: str, path: str) -> None:
    client = app.test_client()
    with client.session_transaction() as session:
        session["user"] = "admin"
        session["role"] = "admin"
        session["approved"] = True
    response = client.get(path)
    if response.status_code != 200:
        print(f"skip {name}: HTTP {response.status_code}")
        return
    html = response.get_data(as_text=True)

    # Flask already rendered url_for -> "/static/style.css"; repoint at the CSS under test
    html = re.sub(r'href="/static/style\.css[^"]*"', f'href="{CSS.as_posix()}"', html)
    # keep app.js, but feed it data instead of the live API. In LIVE mode that data
    # is the app's real /api/data payload (all airports in the database), otherwise
    # the small fixture above. A plain static server has no session, so a real fetch
    # would 401 and app.js would bounce to /login.
    data = FIXTURE
    if LIVE:
        api = client.get("/api/data")
        if api.status_code == 200:
            data = api.get_json()
        else:
            print(f"  warn: /api/data -> HTTP {api.status_code}, memakai fixture")
    stub = (
        "<script>\nvar __api = "
        + json.dumps(data)
        + ";\nwindow.fetch = function (url) {\n"
        # panggilan lain (mis. garis pantai di /static/data/) dibiarkan sungguhan,
        # jadi berkas lokalnya tetap dimuat
        '  if (String(url).indexOf("/api/data") < 0) return window.__realFetch(url);\n'
        "  return Promise.resolve({status: 200, json: function () "
        "{\n    return Promise.resolve(__api);\n  }});\n};\n</script>\n"
    )
    # __realFetch harus disimpan sebelum fetch ditimpa
    html = html.replace(
        '<script src="/static/app.js"></script>',
        "<script>window.__realFetch = window.fetch.bind(window);</script>\n" + stub
        + '<script src="/static/app.js"></script>',
    )
    out = ROOT / f"_preview_{name}{SUFFIX}.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.name} (css={CSS.as_posix()}, airports={len(data['airports'])}, {len(html)} bytes)")


preview("dashboard", "/dashboard")
preview("admin", "/admin")
preview("login", "/login")
preview("register", "/register")
